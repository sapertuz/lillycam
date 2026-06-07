"""Tests for Flask routes using the test client."""

import pytest
from unittest.mock import MagicMock

from lillycam.app import create_app


@pytest.fixture()
def client():
    """Flask test client with mocked hardware."""
    camera = MagicMock()
    camera.get_frame.return_value = b"\xff\xd8\xff\xe0test"
    stepper = MagicMock()
    servo = MagicMock()
    servo.angle = 90.0
    display = MagicMock()

    app = create_app(camera=camera, stepper=stepper, servo=servo, display=display)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, stepper, servo, display


def test_index(client):
    """GET / returns the main page."""
    c, *_ = client
    res = c.get("/")
    assert res.status_code == 200
    assert b"LillyCam" in res.data


def test_dispense(client):
    """POST /dispense calls stepper.dispense() and records in display."""
    c, stepper, _, display = client
    res = c.post("/dispense")
    assert res.status_code == 200
    stepper.dispense.assert_called_once()
    display.record_dispense.assert_called_once()


def test_rotate(client):
    """POST /rotate calls servo.move_to() with the requested angle."""
    c, _, servo, _ = client
    res = c.post("/rotate", json={"angle": 45})
    assert res.status_code == 200
    servo.move_to.assert_called_once_with(45.0)


def test_rotate_defaults_to_90(client):
    """POST /rotate with no body defaults to 90 degrees."""
    c, _, servo, _ = client
    res = c.post("/rotate", json={})
    assert res.status_code == 200
    servo.move_to.assert_called_once_with(90.0)


def test_capture(client):
    """POST /capture calls camera.capture_still()."""
    from pathlib import Path
    c, *_ = client
    cam = client[0].application.camera
    cam.capture_still.return_value = Path("/home/admin/captures/capture_20250101_120000.jpg")
    res = c.post("/capture")
    assert res.status_code == 200
    assert b"capture_" in res.data
