"""Tests for Flask routes using the test client."""

import pytest
from unittest.mock import MagicMock

from lillycam.app import create_app
from lillycam.control import lock


@pytest.fixture()
def client():
    """Flask test client with mocked hardware that already holds control."""
    lock.reset()
    camera = MagicMock()
    camera.get_frame.return_value = b"\xff\xd8\xff\xe0test"
    stepper = MagicMock()
    servo = MagicMock()
    servo.angle = 90.0
    display = MagicMock()

    app = create_app(camera=camera, stepper=stepper, servo=servo, display=display)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/session/claim")  # this client becomes the controller
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


def test_camera_state_reports_streaming(client):
    """GET /camera reflects the camera's is_streaming flag."""
    c, *_ = client
    cam = client[0].application.camera
    cam.is_streaming = False
    assert c.get("/camera").get_json() == {"on": False}
    cam.is_streaming = True
    assert c.get("/camera").get_json() == {"on": True}


def test_camera_on(client):
    """POST /camera/on starts the stream and wakes the OLED cat."""
    c, _, _, display = client
    cam = client[0].application.camera
    res = c.post("/camera/on")
    assert res.status_code == 200
    assert res.get_json() == {"on": True}
    cam.start_stream.assert_called_once()
    display.set_camera.assert_called_once_with(True)


def test_camera_off(client):
    """POST /camera/off stops the stream and sleeps the OLED cat."""
    c, _, _, display = client
    cam = client[0].application.camera
    res = c.post("/camera/off")
    assert res.status_code == 200
    assert res.get_json() == {"on": False}
    cam.stop_stream.assert_called_once()
    display.set_camera.assert_called_once_with(False)


def test_stream_off_returns_503(client):
    """GET /stream returns 503 when the camera is off (and we hold control)."""
    c, *_ = client
    client[0].application.camera.is_streaming = False
    res = c.get("/stream")
    assert res.status_code == 503


# --- Single-connection control lock ---

def test_second_device_is_locked_out(client):
    """A second device cannot claim or control while the first holds it."""
    c, *_ = client
    other = c.application.test_client()  # separate cookie jar = separate device
    claim = other.post("/session/claim").get_json()
    assert claim == {"granted": False, "in_use": True}
    # And every control action is blocked with 423 Locked.
    assert other.post("/dispense").status_code == 423
    assert other.post("/rotate", json={"angle": 10}).status_code == 423
    assert other.get("/stream").status_code == 423


def test_take_control_bumps_previous_holder(client):
    """A forced claim takes over; the old holder's heartbeat then fails."""
    c, *_ = client
    other = c.application.test_client()
    assert other.post("/session/claim", json={"force": True}).get_json()["granted"] is True
    # Original controller has lost the slot.
    assert c.post("/session/heartbeat").status_code == 423
    # New controller can now drive the hardware.
    assert other.post("/dispense").status_code == 200


def test_release_frees_the_slot(client):
    """Releasing control lets another device claim it normally."""
    c, *_ = client
    c.post("/session/release")
    other = c.application.test_client()
    assert other.post("/session/claim").get_json()["granted"] is True
