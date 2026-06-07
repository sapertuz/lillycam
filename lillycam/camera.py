"""picamera2 wrapper for LillyCam.

Provides MJPEG streaming and full-resolution still capture.
Stream resolution: 640x480 @ 15fps (configurable via config.py).
Still resolution: 3280x2464 (Pi Camera v2 full sensor).

Still capture uses a stop-capture-restart pattern because picamera2
does not support simultaneous stream + full-res still on the Zero W.
"""

import io
import logging
import threading
import time  # for AGC settle delay in capture_still
from datetime import datetime
from pathlib import Path

from lillycam import config

log = logging.getLogger(__name__)


class Camera:
    """Manages the Pi Camera v2 for streaming and still capture."""

    def __init__(self) -> None:
        self._cam = None
        self._lock = threading.Lock()
        self._streaming = False

    def start_stream(self) -> None:
        """Start MJPEG streaming at configured resolution."""
        from picamera2 import Picamera2
        from picamera2.encoders import MJPEGEncoder
        from picamera2.outputs import FileOutput

        with self._lock:
            if self._streaming:
                return
            self._cam = Picamera2()
            stream_cfg = self._cam.create_video_configuration(
                main={"size": (config.STREAM_WIDTH, config.STREAM_HEIGHT)},
                raw={"size": (1640, 1232)},  # force sensor mode with full crop_limits
                controls={"FrameRate": config.STREAM_FPS},
            )
            self._cam.configure(stream_cfg)
            self._output = _StreamOutput()
            self._encoder = MJPEGEncoder()
            self._cam.options["quality"] = 70  # lower quality = smaller frames
            self._cam.start_recording(self._encoder, FileOutput(self._output))
            self._streaming = True
            log.info(
                "Stream started: %dx%d @ %dfps",
                config.STREAM_WIDTH,
                config.STREAM_HEIGHT,
                config.STREAM_FPS,
            )

    def stop_stream(self) -> None:
        """Stop MJPEG streaming and release the camera."""
        with self._lock:
            if not self._streaming:
                return
            self._cam.stop_recording()
            self._cam.close()
            self._cam = None
            self._streaming = False
            log.info("Stream stopped")

    def get_frame(self, timeout: float = 1.0) -> bytes:
        """Block until a new MJPEG frame is available, then return it."""
        return self._output.wait_frame(timeout)

    def capture_still(self) -> Path:
        """Capture a full-resolution still.

        Stops the stream, captures at full sensor resolution, then restarts.
        Saves to config.CAPTURE_DIR with a timestamp filename.
        Returns the path to the saved image.
        """
        was_streaming = self._streaming
        if was_streaming:
            self.stop_stream()

        config.CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = config.CAPTURE_DIR / f"capture_{timestamp}.jpg"

        from picamera2 import Picamera2

        cam = Picamera2()
        still_cfg = cam.create_still_configuration(
            main={"size": (config.STILL_WIDTH, config.STILL_HEIGHT)}
        )
        cam.configure(still_cfg)
        cam.start()
        time.sleep(2)  # let AGC/AWB settle before capture
        cam.capture_file(str(path))
        cam.close()
        log.info("Still saved: %s", path)

        if was_streaming:
            self.start_stream()

        return path

    def close(self) -> None:
        """Release camera resources."""
        self.stop_stream()


class _StreamOutput(io.BufferedIOBase):
    """Thread-safe io.BufferedIOBase buffer for the latest MJPEG frame.

    picamera2's FileOutput requires io.BufferedIOBase, not a plain object.
    """

    def __init__(self) -> None:
        self.frame: bytes = b""
        self._cond = threading.Condition()

    def write(self, buf: bytes) -> int:
        if buf.startswith(b"\xff\xd8"):  # JPEG start-of-image marker
            with self._cond:
                self.frame = buf
                self._cond.notify_all()
        return len(buf)

    def wait_frame(self, timeout: float = 1.0) -> bytes:
        """Block until a new frame arrives (avoids busy-spin in the stream route)."""
        with self._cond:
            self._cond.wait(timeout=timeout)
            return self.frame
