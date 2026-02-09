"""
Text-to-Speech module using Coqui TTS.
Generates speech audio and plays it.
"""
import os
import sys
import logging
import threading

log = logging.getLogger(__name__)

# Ensure espeak-ng is on PATH (Windows install location)
_ESPEAK_DIR = r"C:\Program Files\eSpeak NG"
if os.path.isdir(_ESPEAK_DIR) and _ESPEAK_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ESPEAK_DIR + os.pathsep + os.environ.get("PATH", "")
    log.info(f"Added espeak-ng to PATH: {_ESPEAK_DIR}")

# Lazy-loaded TTS engine singleton
_tts_engine = None
_lock = threading.Lock()


def _get_engine():
    """Load TTS model once, cache it."""
    global _tts_engine
    if _tts_engine is None:
        with _lock:
            if _tts_engine is None:
                from TTS.api import TTS as CoquiTTS
                from config import TTS_MODEL
                log.info(f"Loading TTS model '{TTS_MODEL}'...")
                _tts_engine = CoquiTTS(model_name=TTS_MODEL, progress_bar=False)
                log.info("TTS model loaded.")
    return _tts_engine


def warmup_tts():
    """
    Pre-load TTS model and run a dummy synthesis.
    This forces weight loading + JIT compilation so the first real
    TTS call is fast (typically cuts cold-start from ~13s to ~6s).
    """
    import tempfile

    try:
        engine = _get_engine()
        tmp_path = os.path.join(tempfile.gettempdir(), "_tts_warmup.wav")
        from config import TTS_SPEAKER
        log.info("TTS warmup: running dummy synthesis...")
        engine.tts_to_file(
            text="Warming up the voice engine.",
            file_path=tmp_path,
            speaker=TTS_SPEAKER,
        )
        log.info("TTS warmup complete — model is hot.")
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception as e:
        log.warning(f"TTS warmup failed (non-critical): {e}")


def speak(text, block=True):
    """
    Convert text to speech and play it.
    block=True: waits until playback finishes.
    """
    if not text or not text.strip():
        return

    from config import OUTPUT_WAV, TTS_SPEAKER

    # Clean text for TTS (remove markdown, emojis, etc.)
    clean = _clean_for_speech(text)
    if not clean:
        return

    try:
        engine = _get_engine()

        # Generate wav file
        engine.tts_to_file(
            text=clean,
            file_path=OUTPUT_WAV,
            speaker=TTS_SPEAKER,
        )

        # Play it
        _play_audio(OUTPUT_WAV, block=block)
        # Clean up — file is disposable after playback
        _remove_wav(OUTPUT_WAV)
    except Exception as e:
        log.error(f"TTS error: {e}")
        # Fallback: just print the text
        print(f"\n🔇 [TTS failed, text]: {text}")


def split_by_sentence(text, max_sentences=2):
    """
    Split text into chunks of at most `max_sentences` sentences.
    Returns a list of chunk strings.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    for i in range(0, len(sentences), max_sentences):
        chunk = " ".join(sentences[i:i + max_sentences])
        chunks.append(chunk)
    return chunks


# ── Pipelined TTS: synthesize behind playback ───────────────
_synth_lock = threading.Lock()  # Coqui is NOT thread-safe


def _synth_chunk(text, wav_path):
    """Synthesize `text` to `wav_path` (thread-safe via lock)."""
    from config import TTS_SPEAKER
    try:
        engine = _get_engine()
        with _synth_lock:
            engine.tts_to_file(text=text, file_path=wav_path, speaker=TTS_SPEAKER)
        return True
    except Exception as e:
        log.error(f"Synth error: {e}")
        return False


def speak_pipelined(sentence_iter, print_fn=None):
    """
    Consume a sentence generator and pipeline TTS:
      Stream LLM tokens → detect sentence boundary →
      synthesize sentence 1 → start playing →
      synthesize sentence 2 while sentence 1 plays → ...

    This is the single biggest UX win:
      Before: LLM wait 8s → TTS wait 6s → hear voice at 14s
      After:  first sentence ~2s → hear voice at ~4s

    sentence_iter: iterable yielding (sentence_text, full_reply_so_far)
    print_fn:      optional callback for printing each sentence as it arrives
    Returns:       the complete reply text.
    """
    from config import OUTPUT_WAV

    base, ext = os.path.splitext(OUTPUT_WAV)
    full_reply = ""
    chunk_idx = 0

    # Stores (wav_path, thread) for the sentence being synthesized in background
    pending = None    # (thread, wav_path) | None
    prev_wav = None   # path of the WAV currently playing (to delete after)

    try:
        for sentence, full_so_far in sentence_iter:
            full_reply = full_so_far
            if print_fn:
                print_fn(sentence)

            clean = _clean_for_speech(sentence)
            if not clean:
                continue

            wav_path = f"{base}_pipe{chunk_idx}{ext}"
            chunk_idx += 1

            if pending is None:
                # ── First sentence: synth synchronously, play non-blocking ──
                ok = _synth_chunk(clean, wav_path)
                if ok:
                    _play_audio(wav_path, block=False)
                    prev_wav = wav_path
                    pending = "playing"
            else:
                # ── Subsequent sentences: synth THIS one synchronously,
                #    wait for PREVIOUS audio to finish, then play THIS one ──
                ok = _synth_chunk(clean, wav_path)
                # Wait for previous playback to finish
                try:
                    import sounddevice as sd
                    sd.wait()
                except Exception:
                    pass
                # Delete the previous WAV — it's done playing
                _remove_wav(prev_wav)
                # Now play the just-synthesized sentence
                if ok:
                    _play_audio(wav_path, block=False)
                    prev_wav = wav_path

        # ── Wait for last sentence to finish playing ──
        if pending is not None:
            try:
                import sounddevice as sd
                sd.wait()
            except Exception:
                pass
            _remove_wav(prev_wav)

    except Exception as e:
        log.error(f"Pipeline TTS error: {e}")

    return full_reply


def _remove_wav(path):
    """Silently delete a wav file if it exists."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _play_audio(filepath, block=True):
    """Play a wav file using sounddevice."""
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav
        import numpy as np

        sr, data = wav.read(filepath)
        # Normalize if needed
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0

        sd.play(data, sr)
        if block:
            sd.wait()
    except Exception as e:
        log.error(f"Audio playback error: {e}")
        # Fallback: try system command
        try:
            os.system(f'powershell -c "(New-Object Media.SoundPlayer \'{filepath}\').PlaySync()"')
        except Exception:
            log.error("All playback methods failed.")


def _clean_for_speech(text):
    """Remove characters that cause TTS issues."""
    import re
    # Remove markdown formatting
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'`[^`]*`', '', text)
    # Remove emojis (basic range)
    text = re.sub(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]',
        '', text
    )
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate very long text (TTS can choke)
    if len(text) > 300:
        # Find sentence boundary near 300 chars
        idx = text.rfind('.', 0, 300)
        if idx > 100:
            text = text[:idx + 1]
        else:
            text = text[:300] + "."
    return text
