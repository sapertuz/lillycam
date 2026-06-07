"""Test MJPEG streaming from Pi Camera v2.

Starts a Flask server with an MJPEG stream at http://<pi-ip>:8080.
Open that URL in a browser to verify the stream.
Press Ctrl-C to stop.

Usage:
    python examples/test_stream.py
    python examples/test_stream.py --port 8080 --width 640 --height 480 --fps 15
"""

import argparse
import io
import logging
import socket
import threading
import time

from flask import Flask, Response
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class _StreamOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = b""
        self._cond = threading.Condition()

    def write(self, buf):
        if buf.startswith(b"\xff\xd8"):  # JPEG SOI marker
            with self._cond:
                self.frame = buf
                self._cond.notify_all()
        return len(buf)


def get_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "localhost"


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Pi Camera MJPEG stream")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    args = parser.parse_args()

    output = _StreamOutput()

    cam = Picamera2()
    cfg = cam.create_video_configuration(
        main={"size": (args.width, args.height)},
        controls={"FrameRate": args.fps},
    )
    cam.configure(cfg)
    encoder = MJPEGEncoder()
    cam.start_recording(encoder, FileOutput(output))

    ip = get_ip()
    print(f"Stream running at http://{ip}:{args.port}")
    print("Open that URL in a browser. Ctrl-C to stop.")

    app = Flask(__name__)

    @app.route("/")
    def index():
        return f'<img src="/stream" style="max-width:100%"><br><a href="/stream">Direct stream</a>'

    @app.route("/stream")
    def stream():
        def generate():
            while True:
                frame = output.frame
                if frame:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                time.sleep(1 / args.fps)
        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    try:
        app.run(host="0.0.0.0", port=args.port, threaded=True)
    finally:
        cam.stop_recording()
        cam.close()
        print("Stream stopped")


if __name__ == "__main__":
    main()
