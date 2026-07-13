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


# --- Model profile ---
# LillyCam ships in two hardware variants that share this codebase:
#   standard - Pi Zero W v1.1 + Camera Module v2 (single-core; conservative defaults)
#   pro      - Pi Zero 2 W    + Camera Module 3  (quad-core; more headroom)
# LILLYCAM_MODEL selects the per-model defaults below. Precedence for any setting
# is: explicit .env value > model default > shared code default.
LILLYCAM_MODEL: str = _str("LILLYCAM_MODEL", "standard").strip().lower()
if LILLYCAM_MODEL not in ("standard", "pro"):
    LILLYCAM_MODEL = "standard"
IS_PRO: bool = LILLYCAM_MODEL == "pro"

_MODEL_DEFAULTS: dict[str, dict[str, object]] = {
    "standard": {"STREAM_WIDTH": 640, "STREAM_HEIGHT": 480, "STREAM_FPS": 15, "OLED_FPS": 6},
    "pro": {"STREAM_WIDTH": 1280, "STREAM_HEIGHT": 720, "STREAM_FPS": 30, "OLED_FPS": 12},
}


def _model_default(key: str, fallback):
    """Per-model default for a setting, falling back to a shared value."""
    return _MODEL_DEFAULTS.get(LILLYCAM_MODEL, {}).get(key, fallback)


# --- Flask ---
FLASK_HOST: str = _str("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = _int("FLASK_PORT", 5000)
FLASK_DEBUG: bool = _bool("FLASK_DEBUG", False)

# --- Camera ---
CAMERA_AUTOSTART: bool = _bool("CAMERA_AUTOSTART", False)  # off at boot for privacy; turn on from the web UI
CAMERA_SOUND: bool = _bool("CAMERA_SOUND", True)  # play a chirp when the camera turns on
STREAM_WIDTH: int = _int("STREAM_WIDTH", _model_default("STREAM_WIDTH", 640))
STREAM_HEIGHT: int = _int("STREAM_HEIGHT", _model_default("STREAM_HEIGHT", 480))
STREAM_FPS: int = _int("STREAM_FPS", _model_default("STREAM_FPS", 15))
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
OLED_FPS: int = _int("OLED_FPS", _model_default("OLED_FPS", 6))  # per-model (standard 6, pro 12)

# --- PWA / Web Push (experimental) ---
# The web UI ships as an installable PWA (manifest + service worker + icons).
# Home-screen install is harmless, so it is on by default. Web Push is opt-in:
# it needs the pywebpush dependency and only works over HTTPS (Tailscale cert),
# and on iOS 16.4+ only after the app is added to the Home Screen.
PWA_ENABLED: bool = _bool("PWA_ENABLED", True)
PUSH_ENABLED: bool = _bool("PUSH_ENABLED", False)
PUSH_CONTACT: str = _str("PUSH_CONTACT", "mailto:admin@example.com")  # VAPID "sub" claim
# Keys + subscriptions live outside the code tree so redeploys do not wipe them.
PUSH_STATE_DIR: Path = Path(_str("PUSH_STATE_DIR", str(Path.home() / ".lillycam")))
