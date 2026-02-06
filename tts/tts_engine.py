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

    except Exception as e:
        log.error(f"TTS error: {e}")
        # Fallback: just print the text
        print(f"\n🔇 [TTS failed, text]: {text}")


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
    if len(text) > 500:
        # Find sentence boundary near 500 chars
        idx = text.rfind('.', 0, 500)
        if idx > 200:
            text = text[:idx + 1]
        else:
            text = text[:500] + "."
    return text
