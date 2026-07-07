"""Runtime configuration for LillyCam.

Loads values from .env (if present) with sensible defaults.
All application code should import settings from here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, default))


def _bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


def _str(key: str, default: str) -> str:
    return os.getenv(key, default)


# --- Flask ---
FLASK_HOST: str = _str("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = _int("FLASK_PORT", 5000)
FLASK_DEBUG: bool = _bool("FLASK_DEBUG", False)

# --- Camera ---
CAMERA_AUTOSTART: bool = _bool("CAMERA_AUTOSTART", False)  # off at boot for privacy; turn on from the web UI
CAMERA_SOUND: bool = _bool("CAMERA_SOUND", True)  # play a chirp when the camera turns on
STREAM_WIDTH: int = _int("STREAM_WIDTH", 640)
STREAM_HEIGHT: int = _int("STREAM_HEIGHT", 480)
STREAM_FPS: int = _int("STREAM_FPS", 15)
STILL_WIDTH: int = _int("STILL_WIDTH", 3280)
STILL_HEIGHT: int = _int("STILL_HEIGHT", 2464)
CAPTURE_DIR: Path = Path(_str("CAPTURE_DIR", str(Path.home() / "captures")))

# --- Stepper ---
STEPPER_STEPS_PER_DISPENSE: int = _int("STEPPER_STEPS_PER_DISPENSE", 700)  # 28BYJ-48: 2048 full-steps/rev
STEPPER_STEP_DELAY: float = _float("STEPPER_STEP_DELAY", 0.002)

# --- Servo ---
SERVO_MIN_ANGLE: int = _int("SERVO_MIN_ANGLE", 0)
SERVO_MAX_ANGLE: int = _int("SERVO_MAX_ANGLE", 180)
SERVO_DEFAULT_ANGLE: int = _int("SERVO_DEFAULT_ANGLE", 90)

# --- Audio ---
AUDIO_ENABLED: bool = _bool("AUDIO_ENABLED", True)  # set to false to disable mic+speaker
AUDIO_SAMPLE_RATE: int = _int("AUDIO_SAMPLE_RATE", 48000)  # googlevoicehat I2S requires 48000
AUDIO_CHANNELS: int = _int("AUDIO_CHANNELS", 1)
AUDIO_RECORD_SECONDS: int = _int("AUDIO_RECORD_SECONDS", 5)
AUDIO_PLAYBACK_GAIN: float = _float("AUDIO_PLAYBACK_GAIN", 2.0)  # linear gain applied before playback (1.0 = unity)

# --- TLS (optional, for HTTPS via Tailscale cert) ---
# Set these to enable HTTPS so the browser allows microphone access (PTT).
# Get certs with: sudo tailscale cert <your-tailscale-hostname>
TAILSCALE_CERT: str | None = _str("TAILSCALE_CERT", "") or None
TAILSCALE_KEY: str | None = _str("TAILSCALE_KEY", "") or None

# --- Control lock ---
CONTROL_TIMEOUT: float = _float("CONTROL_TIMEOUT", 15.0)  # seconds before an idle controller is auto-released
CAMERA_OFF_ON_IDLE: bool = _bool("CAMERA_OFF_ON_IDLE", True)  # turn the camera off when the last controller leaves

# --- OLED ---
OLED_WIDTH: int = _int("OLED_WIDTH", 128)
OLED_HEIGHT: int = _int("OLED_HEIGHT", 32)
OLED_ANIMATE: bool = _bool("OLED_ANIMATE", True)  # animated cat face (set false for static text only)
OLED_FPS: int = _int("OLED_FPS", 6)  # animation refresh rate (keep low; single-core Pi)
