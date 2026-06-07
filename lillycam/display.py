"""SSD1306 OLED status display for LillyCam.

Drives a 128x32 OLED via I2C using luma.oled.
Displays three lines of status:
  - Line 1: local IP address
  - Line 2: URL (IP:port)
  - Line 3: last dispense time
"""

import logging
import socket
from datetime import datetime

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

from lillycam import config

log = logging.getLogger(__name__)

_I2C_ADDRESS = 0x3C
_I2C_PORT = 1  # /dev/i2c-1


class Display:
    """Manages the SSD1306 OLED status display."""

    def __init__(self) -> None:
        serial = i2c(port=_I2C_PORT, address=_I2C_ADDRESS)
        self._device = ssd1306(
            serial,
            width=config.OLED_WIDTH,
            height=config.OLED_HEIGHT,
        )
        self._last_dispense: str = "never"
        self._ip: str = _get_ip()
        self._port: int = 5000

        log.info(
            "Display initialized: %dx%d at I2C 0x%02X",
            config.OLED_WIDTH,
            config.OLED_HEIGHT,
            _I2C_ADDRESS,
        )

    def show_status(self, ip: str | None = None, port: int | None = None) -> None:
        """Render current status on the OLED.

        Args:
            ip: IP address to display. Cached value used if None.
            port: Flask port. Cached value used if None.
        """
        if ip is not None:
            self._ip = ip
        if port is not None:
            self._port = port

        line2 = f"{self._ip}:{self._port}"
        self._render(self._ip, line2, f"last: {self._last_dispense}")

    def show_message(self, text: str) -> None:
        """Display a single message (for boot/error states).

        Args:
            text: Text to display.
        """
        with canvas(self._device) as draw:
            draw.text((0, 10), text, fill="white")

    def record_dispense(self) -> None:
        """Update the last-dispense timestamp and refresh the display."""
        self._last_dispense = datetime.now().strftime("%H:%M:%S")
        self.show_status()

    def clear(self) -> None:
        """Clear the display."""
        self._device.clear()

    def close(self) -> None:
        """Clear display and release I2C resources."""
        self.clear()
        self._device.cleanup()
        log.info("Display closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render(self, line1: str, line2: str, line3: str) -> None:
        with canvas(self._device) as draw:
            draw.text((0, 0),  line1, fill="white")
            draw.text((0, 11), line2, fill="white")
            draw.text((0, 22), line3, fill="white")


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
