"""Flask route handlers for LillyCam.

All routes are registered on a Blueprint so the app factory
can include them cleanly. Hardware is accessed via current_app.
"""

import logging

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_from_directory

log = logging.getLogger(__name__)

bp = Blueprint("lillycam", __name__)


# --- Pages ---

@bp.route("/")
def index():
    """Main control page."""
    return render_template("index.html")


# --- Video stream ---

@bp.route("/stream")
def stream():
    """MJPEG stream endpoint. Open in <img src="/stream">."""
    cam = current_app.camera
    if cam is None:
        return "Camera not available", 503

    def generate():
        while True:
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
    from lillycam import audio, config as cfg
    if not cfg.AUDIO_ENABLED:
        return jsonify(error="Audio disabled"), 503
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
