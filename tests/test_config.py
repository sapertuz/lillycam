"""Tests for lillycam.config."""

import os
import importlib


def test_defaults():
    """Config provides expected defaults when no .env is present."""
    import lillycam.config as cfg
    assert cfg.FLASK_PORT == 5000
    assert cfg.STREAM_WIDTH == 640
    assert cfg.STREAM_HEIGHT == 480
    assert cfg.STREAM_FPS == 15
    assert cfg.STEPPER_STEPS_PER_DISPENSE == 512
    assert cfg.SERVO_DEFAULT_ANGLE == 90
    assert cfg.OLED_WIDTH == 128
    assert cfg.OLED_HEIGHT == 32


def test_env_override(monkeypatch):
    """Environment variables override defaults."""
    monkeypatch.setenv("FLASK_PORT", "8080")
    monkeypatch.setenv("STREAM_WIDTH", "320")
    # Re-import to pick up env changes
    import lillycam.config as cfg
    importlib.reload(cfg)
    assert cfg.FLASK_PORT == 8080
    assert cfg.STREAM_WIDTH == 320
