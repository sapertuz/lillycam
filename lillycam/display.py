"""SSD1306 OLED status display for LillyCam.

Drives a 128x32 OLED via I2C using luma.oled. The left third of the screen
shows an animated cat face (Popcat style); the right shows status text:
  - Line 1: camera state (CAM ON / CAM OFF)
  - Line 2: URL (IP:port)
  - Line 3: last dispense time

The cat sleeps (closed eyes, drifting "z"s) while the camera is off and wakes
up (open eyes, blinking) when it turns on. It "pops" its mouth on events like
a dispense or the camera coming on. Set OLED_ANIMATE=false for static text.
"""

import logging
import socket
import threading
import time
from datetime import datetime

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

from lillycam import config
from lillycam.control import lock

log = logging.getLogger(__name__)

_I2C_ADDRESS = 0x3C
_I2C_PORT = 1  # /dev/i2c-1

_POP_SECONDS = 0.6  # how long the cat holds an open mouth after an event
_BANNER_SECONDS = 1.4  # how long a transient banner (e.g. "CAMERA ON") stays up


class Display:
    """Manages the SSD1306 OLED with an animated cat face and status text."""

    def __init__(self) -> None:
        serial = i2c(port=_I2C_PORT, address=_I2C_ADDRESS)
        self._device = ssd1306(
            serial,
            width=config.OLED_WIDTH,
            height=config.OLED_HEIGHT,
        )

        # Status state (guarded by _lock)
        self._lock = threading.Lock()
        self._last_dispense: str = "never"
        self._ip: str = _get_ip()
        self._port: int = 5000
        self._camera_on: bool = False
        self._message: str | None = "LillyCam booting"  # full-screen override
        self._pop_until: float = 0.0
        self._banner: str | None = None
        self._banner_until: float = 0.0

        self._device_lock = threading.Lock()  # serializes all writes to the OLED
        self._frame = 0
        self._running = False
        self._thread: threading.Thread | None = None

        if config.OLED_ANIMATE:
            self._running = True
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()

        log.info(
            "Display initialized: %dx%d at I2C 0x%02X (animate=%s)",
            config.OLED_WIDTH,
            config.OLED_HEIGHT,
            _I2C_ADDRESS,
            config.OLED_ANIMATE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_status(self, ip: str | None = None, port: int | None = None) -> None:
        """Clear any boot/error message and show the live status + cat face.

        Args:
            ip: IP address to display. Cached value used if None.
            port: Flask port. Cached value used if None.
        """
        with self._lock:
            if ip is not None:
                self._ip = ip
            if port is not None:
                self._port = port
            self._message = None
        self._paint_if_static()

    def show_message(self, text: str) -> None:
        """Display a single full-screen message (for boot/error states)."""
        with self._lock:
            self._message = text
        self._paint_if_static()

    def set_camera(self, on: bool) -> None:
        """Update the camera state shown on the OLED.

        Turning on wakes the cat, pops its mouth, and flashes a banner.
        """
        with self._lock:
            self._camera_on = on
            self._message = None
            self._banner = "CAMERA ON" if on else "CAMERA OFF"
            self._banner_until = time.monotonic() + _BANNER_SECONDS
            if on:
                self._pop_until = time.monotonic() + _POP_SECONDS
        self._paint_if_static()

    def record_dispense(self) -> None:
        """Update the last-dispense timestamp, pop the cat, and refresh."""
        with self._lock:
            self._last_dispense = datetime.now().strftime("%H:%M:%S")
            self._pop_until = time.monotonic() + _POP_SECONDS
        self._paint_if_static()

    def clear(self) -> None:
        """Clear the display."""
        with self._device_lock:
            self._device.clear()

    def close(self) -> None:
        """Stop animation, clear the display, and release I2C resources."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self.clear()
        self._device.cleanup()
        log.info("Display closed")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _animate(self) -> None:
        """Background loop: repaint the screen at OLED_FPS for blinks/pops/zzz."""
        interval = 1.0 / max(1, config.OLED_FPS)
        while self._running:
            try:
                self._paint()
            except Exception as exc:  # never let the OLED thread kill the app
                log.warning("OLED render error: %s", exc)
            self._frame += 1
            time.sleep(interval)

    def _paint_if_static(self) -> None:
        """Repaint immediately when not animating (the loop handles it otherwise)."""
        if not config.OLED_ANIMATE:
            self._paint()

    def _snapshot(self) -> dict:
        """Copy the mutable state under lock so rendering sees a consistent frame."""
        with self._lock:
            return {
                "ip": self._ip,
                "port": self._port,
                "last": self._last_dispense,
                "camera_on": self._camera_on,
                "message": self._message,
                "pop": time.monotonic() < self._pop_until,
                "banner": self._banner if time.monotonic() < self._banner_until else None,
            }

    def _paint(self) -> None:
        s = self._snapshot()
        fps = max(1, config.OLED_FPS)
        # Blink for one frame roughly every 3 seconds while awake.
        blink = s["camera_on"] and config.OLED_ANIMATE and (self._frame % (fps * 3) == 0)
        # Sleeping eyes are always closed; the "z" drifts upward over ~2 seconds.
        z_phase = (self._frame % (fps * 2)) / (fps * 2)

        with self._device_lock:
            with canvas(self._device) as draw:
                if s["message"]:
                    _draw_centered(draw, s["message"])
                    return
                if s["banner"]:
                    _draw_centered(draw, s["banner"])
                    return
                _draw_cat(
                    draw,
                    awake=s["camera_on"],
                    blink=blink,
                    mouth_open=s["pop"],
                    z_phase=z_phase,
                    animate=config.OLED_ANIMATE,
                )
                _draw_status(draw, s["camera_on"], lock.in_use(), s["last"])


# ----------------------------------------------------------------------
# Drawing helpers (module-level, no device state)
# ----------------------------------------------------------------------

# The cat occupies the left ~34px; status text fills the rest.
_TEXT_X = 38


def _draw_centered(draw, text: str) -> None:
    """Draw a single line of text roughly centered on the 128x32 screen."""
    x = max(0, (config.OLED_WIDTH - len(text) * 6) // 2)
    draw.text((x, 12), text, fill="white")


def _draw_status(draw, camera_on: bool, in_use: bool, last: str) -> None:
    """Draw the three status lines to the right of the cat face.

    Line 1: camera state. Line 2: whether a device is connected. Line 3: last dispense.
    """
    if camera_on:
        draw.rectangle((_TEXT_X, 0, _TEXT_X + 52, 9), fill="white")
        draw.text((_TEXT_X + 3, 1), "CAM ON", fill="black")
    else:
        draw.text((_TEXT_X, 1), "CAM OFF", fill="white")
    draw.text((_TEXT_X, 11), "in use" if in_use else "idle", fill="white")
    draw.text((_TEXT_X, 22), f"last {last}", fill="white")


def _draw_cat(draw, *, awake: bool, blink: bool, mouth_open: bool,
              z_phase: float, animate: bool) -> None:
    """Draw the cat face in the left region.

    Args:
        awake: eyes open (camera on) vs closed and sleeping (camera off).
        blink: momentarily close the eyes even while awake.
        mouth_open: Popcat-style open mouth (used on events).
        z_phase: 0..1 drift position for the sleeping "z".
        animate: when False, skip the drifting "z" (static mode).
    """
    # Ears (filled triangles)
    draw.polygon([(4, 9), (12, 9), (6, 2)], outline="white", fill="white")
    draw.polygon([(20, 9), (28, 9), (26, 2)], outline="white", fill="white")
    # Head
    draw.ellipse((2, 7, 30, 31), outline="white", fill="black")

    # Eyes
    eyes_closed = blink or not awake
    if eyes_closed:
        draw.line((8, 18, 13, 18), fill="white")
        draw.line((19, 18, 24, 18), fill="white")
    else:
        draw.ellipse((9, 15, 13, 20), outline="white", fill="white")
        draw.ellipse((19, 15, 23, 20), outline="white", fill="white")

    # Nose
    draw.polygon([(14, 21), (18, 21), (16, 23)], outline="white", fill="white")

    # Mouth
    if mouth_open:
        draw.ellipse((12, 23, 20, 30), outline="white", fill="white")  # Popcat "pop"
    else:
        draw.line((16, 23, 16, 25), fill="white")
        draw.line((16, 25, 13, 27), fill="white")
        draw.line((16, 25, 19, 27), fill="white")

    # Whiskers
    draw.line((0, 22, 8, 21), fill="white")
    draw.line((0, 25, 8, 24), fill="white")
    draw.line((24, 21, 32, 22), fill="white")
    draw.line((24, 24, 32, 25), fill="white")

    # Sleeping "z" drifting up to the right of the head
    if not awake:
        zy = 10 - int(z_phase * 6) if animate else 6
        draw.text((30, zy), "z", fill="white")


def _get_tailscale_ip() -> str | None:
    """Return the Tailscale IP (100.x.x.x) if tailscale0 interface is active."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", "tailscale0"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode()
        for part in out.split():
            if part.startswith("100."):
                return part.split("/")[0]
    except Exception:
        pass
    return None


def _get_ip() -> str:
    """Return Tailscale IP if available, otherwise the primary local IPv4 address."""
    ts = _get_tailscale_ip()
    if ts:
        return ts
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "no network"
