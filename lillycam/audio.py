"""Half-duplex audio for LillyCam.

The Pi Zero W cannot handle full-duplex I2S reliably, so mic and speaker
share the I2S bus in a walkie-talkie (push-to-talk) pattern:
  - record() captures from the INMP441 mic.
  - play() plays through the MAX98357A amp.

Both use sounddevice with the ALSA I2S devices configured in /etc/asound.conf.
"""

import logging
import math
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

from lillycam import config

log = logging.getLogger(__name__)

# ALSA device names as configured in config/asound.conf
_MIC_DEVICE = "mic"
_AMP_DEVICE = "speaker"


def record(seconds: float | None = None, device: str = _MIC_DEVICE) -> np.ndarray:
    """Record audio from the INMP441 microphone.

    Args:
        seconds: Recording duration in seconds. Defaults to config.AUDIO_RECORD_SECONDS.
        device: ALSA device name for the microphone.

    Returns:
        NumPy array of shape (samples, channels) with dtype float32.
    """
    if seconds is None:
        seconds = config.AUDIO_RECORD_SECONDS
    log.info("Recording %.1fs from '%s'", seconds, device)
    data = sd.rec(
        int(seconds * config.AUDIO_SAMPLE_RATE),
        samplerate=config.AUDIO_SAMPLE_RATE,
        channels=config.AUDIO_CHANNELS,
        dtype="float32",
        device=device,
        blocking=True,
    )
    log.info("Recording complete (%d samples)", len(data))
    return data


def play(data: np.ndarray, device: str = _AMP_DEVICE, samplerate: int | None = None) -> None:
    """Play audio through the MAX98357A amplifier.

    Args:
        data: NumPy float32 audio array (samples, channels) or (samples,).
        device: ALSA device name for the amplifier.
        samplerate: Sample rate in Hz. Defaults to config.AUDIO_SAMPLE_RATE.
    """
    if samplerate is None:
        samplerate = config.AUDIO_SAMPLE_RATE
    # Apply software gain and clip to prevent distortion
    gain = config.AUDIO_PLAYBACK_GAIN
    if gain != 1.0:
        data = np.clip(data * gain, -1.0, 1.0)
    # asound.conf plug slave handles mono->stereo, but duplicate here as fallback
    if data.ndim == 1 or data.shape[1] == 1:
        flat = data.flatten()
        data = np.column_stack([flat, flat])
    log.info("Playing %d samples through '%s' at %dHz (gain=%.1f)", len(data), device, samplerate, gain)
    sd.play(data, samplerate=samplerate, device=device, blocking=True)
    log.info("Playback complete")


def chirp(device: str = _AMP_DEVICE) -> None:
    """Play a short ascending two-note chirp (used as the camera-on indicator).

    Blocks for about 0.3s. Use chirp_async() to fire-and-forget from a request.
    """
    rate = config.AUDIO_SAMPLE_RATE
    tone = np.concatenate([_tone(880.0, 0.12, rate), _tone(1318.5, 0.16, rate)])  # A5 -> E6
    stereo = np.column_stack([tone, tone])  # googlevoicehat I2S driver wants stereo
    log.info("Camera chirp through '%s'", device)
    sd.play(stereo, samplerate=rate, device=device, blocking=True)


def chirp_async() -> None:
    """Play the camera-on chirp on a daemon thread so it never blocks the caller."""
    if not config.AUDIO_ENABLED or not config.CAMERA_SOUND:
        return
    threading.Thread(target=_safe_chirp, daemon=True).start()


def _safe_chirp() -> None:
    try:
        chirp()
    except Exception as exc:  # speaker is non-critical; never crash the request
        log.warning("Chirp failed: %s", exc)


def _tone(freq: float, seconds: float, rate: int, volume: float = 0.5) -> np.ndarray:
    """Generate a sine tone with a 10ms fade in/out to avoid clicks."""
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    tone = (volume * np.sin(2 * math.pi * freq * t)).astype(np.float32)
    fade = int(rate * 0.01)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return tone


def save_wav(data: np.ndarray, path: Path) -> None:
    """Save audio data to a WAV file.

    Args:
        data: NumPy float32 audio array.
        path: Destination file path.
    """
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    int_data = (data * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(config.AUDIO_CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(config.AUDIO_SAMPLE_RATE)
        wf.writeframes(int_data.tobytes())
    log.info("Saved WAV: %s", path)
