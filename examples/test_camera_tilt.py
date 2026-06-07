"""Test ScalerCrop tilt on the Pi Camera v2 (IMX219).

Starts a stream, then steps through tilt positions (full up → center → full down),
pausing at each so you can see the shift in the browser at http://lillycam.local:8080.

Usage:
    .venv/bin/python examples/test_camera_tilt.py
"""

import time
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
import io
import threading
import socketserver
import http.server

# --- Sensor / crop constants (same as camera.py) ---
SENSOR_W = 3280
SENSOR_H = 2464
CROP_W = int(SENSOR_W * 0.85)           # 2788
CROP_H = int(CROP_W * 3 / 4)            # 2091
CROP_X = (SENSOR_W - CROP_W) // 2       # 246
CROP_Y_MAX = SENSOR_H - CROP_H          # 373

STREAM_W, STREAM_H = 640, 480
PORT = 8080


class StreamOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = b""
        self._cond = threading.Condition()

    def write(self, buf):
        if buf.startswith(b"\xff\xd8"):
            with self._cond:
                self.frame = buf
                self._cond.notify_all()
        return len(buf)


output = StreamOutput()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    frame = output.frame
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
            except Exception:
                pass
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><img src='/stream'></body></html>"
            )

    def log_message(self, *_):
        pass


def set_crop(cam, tilt: float):
    """Apply ScalerCrop for given tilt (0.0=up, 0.5=center, 1.0=down)."""
    y = int(CROP_Y_MAX * tilt)
    crop = (CROP_X, y, CROP_W, CROP_H)
    cam.set_controls({"ScalerCrop": crop})
    print(f"  tilt={tilt:.1f}  ScalerCrop={crop}")


def main():
    cam = Picamera2()

    # Print what sensor modes are available
    print("Sensor modes:")
    for i, mode in enumerate(cam.sensor_modes):
        print(f"  [{i}] {mode}")

    cfg = cam.create_video_configuration(
        main={"size": (STREAM_W, STREAM_H)},
        raw={"size": (1640, 1232)},  # force sensor mode 1: crop_limits=(0,0,3280,2464)
        controls={"FrameRate": 15},
    )
    cam.configure(cfg)

    enc = MJPEGEncoder()
    cam.start_recording(enc, FileOutput(output))
    print(f"\nStream started — open http://lillycam.local:{PORT} in your browser\n")

    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("", PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        steps = [
            (0.5, "center (default)"),
            (0.0, "full UP"),
            (0.5, "center"),
            (1.0, "full DOWN"),
            (0.5, "center"),
            (0.25, "quarter UP"),
            (0.75, "quarter DOWN"),
        ]
        for tilt, label in steps:
            print(f"Setting tilt: {label}")
            set_crop(cam, tilt)
            time.sleep(4)

        print("\nDone. Ctrl-C to exit.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        cam.stop_recording()
        cam.close()
        server.shutdown()


if __name__ == "__main__":
    main()
