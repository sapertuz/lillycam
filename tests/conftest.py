"""Pytest fixtures for LillyCam unit tests.

GPIO, picamera2, sounddevice, and luma.oled are mocked so tests
can run on any machine without Pi hardware.
"""

import sys
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub out hardware-only modules before any application imports
# ---------------------------------------------------------------------------

def _make_mock(name: str) -> MagicMock:
    mod = MagicMock()
    mod.__name__ = name
    return mod


# RPi.GPIO
# Note: `import RPi.GPIO as GPIO` binds GPIO via attribute access on the RPi
# package mock, so RPi.GPIO must point at the SAME object as sys.modules["RPi.GPIO"];
# otherwise the code under test drives an auto-created child mock instead of this one.
gpio_mock = _make_mock("RPi.GPIO")
gpio_mock.BCM = 11
gpio_mock.OUT = 0
gpio_mock.LOW = 0
gpio_mock.HIGH = 1
rpi_mock = _make_mock("RPi")
rpi_mock.GPIO = gpio_mock
sys.modules["RPi"] = rpi_mock
sys.modules["RPi.GPIO"] = gpio_mock

# gpiozero
sys.modules["gpiozero"] = _make_mock("gpiozero")

# picamera2
sys.modules["picamera2"] = _make_mock("picamera2")
sys.modules["picamera2.encoders"] = _make_mock("picamera2.encoders")
sys.modules["picamera2.outputs"] = _make_mock("picamera2.outputs")

# luma
sys.modules["luma"] = _make_mock("luma")
sys.modules["luma.core"] = _make_mock("luma.core")
sys.modules["luma.core.interface"] = _make_mock("luma.core.interface")
sys.modules["luma.core.interface.serial"] = _make_mock("luma.core.interface.serial")
sys.modules["luma.core.render"] = _make_mock("luma.core.render")
sys.modules["luma.oled"] = _make_mock("luma.oled")
sys.modules["luma.oled.device"] = _make_mock("luma.oled.device")

# sounddevice
sys.modules["sounddevice"] = _make_mock("sounddevice")

# PIL (used by luma)
sys.modules["PIL"] = _make_mock("PIL")
sys.modules["PIL.ImageFont"] = _make_mock("PIL.ImageFont")

# smbus2
sys.modules["smbus2"] = _make_mock("smbus2")

# pigpio
pigpio_mock = _make_mock("pigpio")
_pi_instance = MagicMock()
_pi_instance.connected = True
pigpio_mock.pi.return_value = _pi_instance
sys.modules["pigpio"] = pigpio_mock


@pytest.fixture()
def gpio():
    """Return the mocked RPi.GPIO module."""
    return gpio_mock
