"""
Speech-to-Text module using faster-whisper.
Records from mic with auto-silence detection, transcribes to text.
"""
import sys
import numpy as np
import sounddevice as sd
import logging
import time

log = logging.getLogger(__name__)

# Lazy-loaded model singleton
_model = None
# Calibrated noise floor (set at first recording)
_noise_floor = None


def _get_model():
    """Load whisper model once and cache it."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE
        log.info(f"Loading Whisper model '{WHISPER_MODEL_SIZE}' on {WHISPER_DEVICE}...")
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
        log.info("Whisper model loaded.")
    return _model


def calibrate_mic():
    """
    Read 1 second of ambient audio to measure the noise floor.
    Sets a dynamic silence threshold slightly above ambient level.
    """
    global _noise_floor
    from config import RECORD_SAMPLERATE, RECORD_CHANNELS
    fs = RECORD_SAMPLERATE
    try:
        print("   (calibrating mic — stay quiet for 1 second)")
        ambient = sd.rec(int(fs * 1), samplerate=fs, channels=RECORD_CHANNELS, dtype="float32")
        sd.wait()
        rms = np.sqrt(np.mean(ambient ** 2))
        # Set threshold at 3x ambient noise so speech clearly exceeds it
        _noise_floor = max(rms * 3.0, 0.008)
        log.info(f"Mic calibrated — ambient RMS={rms:.5f}, threshold={_noise_floor:.5f}")
    except Exception as e:
        log.warning(f"Mic calibration failed: {e}, using default threshold")
        _noise_floor = 0.02


def _get_threshold():
    """Return the silence threshold, calibrating if needed."""
    global _noise_floor
    if _noise_floor is None:
        calibrate_mic()
    return _noise_floor


def record_audio(duration=None, auto_stop=True):
    """
    Record audio from mic.
    If auto_stop=True, stops after sustained silence following speech.
    Returns numpy array of audio samples.
    """
    from config import RECORD_SAMPLERATE, RECORD_CHANNELS, RECORD_DURATION_DEFAULT
    from config import SILENCE_TIMEOUT, MAX_RECORD_SECONDS

    if duration is None:
        duration = RECORD_DURATION_DEFAULT

    fs = RECORD_SAMPLERATE
    channels = RECORD_CHANNELS
    threshold = _get_threshold()

    if auto_stop:
        max_duration = MAX_RECORD_SECONDS
        chunk_duration = 0.3  # 300ms chunks for responsiveness
        chunk_size = int(fs * chunk_duration)
        frames = []
        silence_start = None
        speech_detected = False
        speech_frames = []  # only keep frames from speech onward

        try:
            stream = sd.InputStream(samplerate=fs, channels=channels, dtype="float32")
            stream.start()

            total_recorded = 0.0
            while total_recorded < max_duration:
                chunk, _ = stream.read(chunk_size)
                total_recorded += chunk_duration
                rms = np.sqrt(np.mean(chunk ** 2))

                if rms > threshold:
                    # Speech detected
                    if not speech_detected:
                        speech_detected = True
                        log.info("Speech detected, recording...")
                    silence_start = None
                    speech_frames.append(chunk.copy())
                elif speech_detected:
                    # After speech, now silence
                    speech_frames.append(chunk.copy())  # keep trailing audio
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_TIMEOUT:
                        log.info("Pause detected, stopping recording.")
                        break
                # If no speech yet, don't save (skip ambient noise)

            stream.stop()
            stream.close()

            if not speech_frames:
                log.warning("No speech detected during recording.")
                return np.array([], dtype="float32")

            audio = np.concatenate(speech_frames, axis=0).flatten()
            duration_s = len(audio) / fs
            log.info(f"Captured {duration_s:.1f}s of speech audio.")
            return audio

        except Exception as e:
            log.error(f"Recording error: {e}")
            return np.array([], dtype="float32")
    else:
        # Fixed duration recording
        try:
            log.info(f"Recording for {duration}s...")
            audio = sd.rec(
                int(duration * fs),
                samplerate=fs,
                channels=channels,
                dtype="float32",
            )
            sd.wait()
            return audio.flatten()
        except Exception as e:
            log.error(f"Recording error: {e}")
            return np.array([], dtype="float32")


def transcribe(audio_data=None):
    """
    Transcribe audio to text.
    If audio_data is None, records first.
    Returns transcribed text string.
    """
    if audio_data is None:
        audio_data = record_audio()

    if len(audio_data) == 0:
        log.warning("Empty audio, nothing to transcribe.")
        return ""

    # Check if audio is mostly silence
    rms = np.sqrt(np.mean(audio_data ** 2))
    if rms < 0.005:
        log.warning("Audio is mostly silence.")
        return ""

    try:
        model = _get_model()
        segments, info = model.transcribe(
            audio_data,
            beam_size=5,
            language="en",
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        # Filter out hallucinated short noise transcriptions
        if len(text) <= 2:
            log.warning(f"Transcription too short ('{text}'), treating as silence.")
            return ""
        return text
    except Exception as e:
        log.error(f"Transcription error: {e}")
        return ""


def warmup_stt():
    """Pre-load whisper model and calibrate mic."""
    _get_model()
    calibrate_mic()


def listen():
    """
    One-shot: record + transcribe.
    Returns text string.
    """
    print("\n🎤 Listening... (speak now, stops after you pause)")
    audio = record_audio(auto_stop=True)
    if len(audio) == 0:
        return ""
    print("⏳ Transcribing...")
    text = transcribe(audio)
    return text
