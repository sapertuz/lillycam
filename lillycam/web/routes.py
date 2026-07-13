"""Flask route handlers for LillyCam.

All routes are registered on a Blueprint so the app factory
can include them cleanly. Hardware is accessed via current_app.
"""

import logging
import uuid

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_from_directory, session

from lillycam.control import lock

log = logging.getLogger(__name__)

bp = Blueprint("lillycam", __name__)


# --- Single-connection control lock ---

def _token() -> str:
    """Return this browser's control token, minting one into the session if needed."""
    t = session.get("token")
    if not t:
        t = uuid.uuid4().hex
        session["token"] = t
    return t


def _has_control() -> bool:
    """True if the caller holds control. Refreshes the hold as a side effect."""
    return lock.heartbeat(session.get("token"))


def _locked_response():
    """JSON 423 used by guarded routes when the caller does not hold control."""
    return jsonify(error="LillyCam is controlled by another device"), 423


@bp.route("/session/claim", methods=["POST"])
def session_claim():
    """Claim control. Body {"force": true} takes it over from another device."""
    data = request.get_json(silent=True) or {}
    granted = lock.claim(_token(), force=bool(data.get("force")))
    return jsonify(granted=granted, in_use=lock.in_use())


@bp.route("/session/heartbeat", methods=["POST"])
def session_heartbeat():
    """Keep the hold alive. Returns 423 if this device was taken over."""
    if lock.heartbeat(session.get("token")):
        return jsonify(ok=True)
    return jsonify(ok=False, error="lost"), 423


@bp.route("/session/release", methods=["POST"])
def session_release():
    """Release control (called on page unload via sendBeacon)."""
    lock.release(session.get("token"))
    return jsonify(ok=True)


@bp.route("/session/status")
def session_status():
    """Report whether control is held, and whether by this device."""
    return jsonify(in_use=lock.in_use(), you_hold=lock.is_holder(session.get("token")))


# --- Pages ---

@bp.route("/")
def index():
    """Main control page."""
    from lillycam import config
    _token()  # ensure the session cookie exists before the page claims control
    return render_template(
        "index.html",
        pwa_enabled=config.PWA_ENABLED,
        push_enabled=config.PUSH_ENABLED,
    )


@bp.route("/sw.js")
def service_worker():
    """Serve the service worker from the root so its scope covers the whole app.

    A worker served from /static/ would only control /static/; PWAs need root.
    """
    resp = send_from_directory(current_app.static_folder, "sw.js")
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# --- Video stream ---

@bp.route("/camera")
def camera_state():
    """Return whether the camera/stream is currently on (for UI sync on load)."""
    cam = current_app.camera
    return jsonify(on=bool(cam and cam.is_streaming))


@bp.route("/camera/on", methods=["POST"])
def camera_on():
    """Turn the camera on: start the stream, wake the OLED cat, chirp."""
    if not _has_control():
        return _locked_response()
    cam = current_app.camera
    if cam is None:
        return jsonify(error="Camera not available"), 503
    cam.start_stream()
    if current_app.display:
        current_app.display.set_camera(True)
    # The camera-on chirp is optional: never let a missing audio stack (no
    # PortAudio, or no I2S sound card) block turning the camera on.
    from lillycam import config as cfg
    if cfg.CAMERA_SOUND:
        try:
            from lillycam import audio
            audio.chirp_async()
        except Exception as exc:
            log.warning("Camera-on chirp skipped: %s", exc)
    return jsonify(on=True)


@bp.route("/camera/off", methods=["POST"])
def camera_off():
    """Turn the camera off: stop the stream and put the OLED cat to sleep."""
    if not _has_control():
        return _locked_response()
    cam = current_app.camera
    if cam is None:
        return jsonify(error="Camera not available"), 503
    cam.stop_stream()
    if current_app.display:
        current_app.display.set_camera(False)
    return jsonify(on=False)


@bp.route("/stream")
def stream():
    """MJPEG stream endpoint. Open in <img src="/stream">.

    Restricted to the controlling device (one stream consumer on the Pi Zero).
    Returns 503 when the camera is off so the client can show its placeholder.
    """
    if not _has_control():
        return "LillyCam is controlled by another device", 423
    cam = current_app.camera
    if cam is None or not cam.is_streaming:
        return "Camera is off", 503

    def generate():
        while cam.is_streaming:
            frame = cam.get_frame()
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@bp.route("/capture", methods=["POST"])
def capture():
    """Capture a full-resolution still. Returns JSON with saved path."""
    if not _has_control():
        return _locked_response()
    cam = current_app.camera
    if cam is None:
        return jsonify(error="Camera not available"), 503
    path = cam.capture_still()
    return jsonify(path=str(path))


@bp.route("/captures/<filename>")
def serve_capture(filename):
    """Download a previously captured still image."""
    from lillycam import config
    return send_from_directory(config.CAPTURE_DIR, filename)


# --- Dispenser ---

@bp.route("/dispense", methods=["POST"])
def dispense():
    """Trigger one treat dispense cycle."""
    if not _has_control():
        return _locked_response()
    stepper = current_app.stepper
    if stepper is None:
        return jsonify(error="Stepper not available"), 503
    stepper.dispense()
    display = current_app.display
    if display:
        display.record_dispense()
    return jsonify(ok=True)


@bp.route("/reverse", methods=["POST"])
def reverse():
    """Run the stepper in reverse to unstick the dispenser."""
    if not _has_control():
        return _locked_response()
    stepper = current_app.stepper
    if stepper is None:
        return jsonify(error="Stepper not available"), 503
    stepper.reverse()
    return jsonify(ok=True)


# --- Servo ---

@bp.route("/servo")
def servo_state():
    """Return current servo angle so the UI can sync on page load."""
    servo = current_app.servo
    return jsonify(angle=servo.angle if servo else 90)


@bp.route("/rotate", methods=["POST"])
def rotate():
    """Move the servo to a requested angle.

    JSON body: {"angle": <float>}
    """
    if not _has_control():
        return _locked_response()
    servo = current_app.servo
    if servo is None:
        return jsonify(error="Servo not available"), 503
    data = request.get_json(silent=True) or {}
    angle = float(data.get("angle", 90))
    servo.move_to(angle)
    return jsonify(angle=servo.angle)



# --- Audio ---

@bp.route("/speak", methods=["POST"])
def speak():
    """Receive audio from client and play it through the speaker.

    Expects raw WAV bytes in the request body.
    """
    if not _has_control():
        return _locked_response()
    from lillycam import config as cfg
    if not cfg.AUDIO_ENABLED:
        return jsonify(error="Audio disabled"), 503
    from lillycam import audio
    import numpy as np, io, wave

    body = request.data
    if not body:
        return jsonify(error="No audio data"), 400

    with wave.open(io.BytesIO(body)) as wf:
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0

    audio.play(arr, samplerate=rate)
    return jsonify(ok=True)
