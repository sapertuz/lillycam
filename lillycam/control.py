"""Single-connection control lock for LillyCam.

Only one device may control LillyCam at a time. This keeps a single MJPEG
stream consumer on the single-core Pi Zero and prevents two clients from
fighting over the servo and dispenser.

A client "holds" control by presenting a session token. The holder must send
periodic heartbeats; if they stop for CONTROL_TIMEOUT seconds (tab closed,
walked away) the slot auto-releases. A new client can force a takeover, which
bumps the previous holder to a locked screen on their next request.

This module exposes a process-wide singleton, ``lock``, shared by the web
routes and the OLED display.
"""

import threading
import time

from lillycam import config


class ControlLock:
    """Tracks which session token currently holds control (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._last_seen: float = 0.0

    def _holder(self) -> str | None:
        """Return the current holder, clearing it if its heartbeat expired.

        Caller must hold self._lock.
        """
        if self._token is not None and (time.monotonic() - self._last_seen) > config.CONTROL_TIMEOUT:
            self._token = None
        return self._token

    def claim(self, token: str | None, force: bool = False) -> bool:
        """Try to acquire control for ``token``.

        Granted if the slot is free, already held by this token, or ``force``
        is set (takeover). Returns True if this token now holds control.
        """
        if not token:
            return False
        with self._lock:
            holder = self._holder()
            if holder is None or holder == token or force:
                self._token = token
                self._last_seen = time.monotonic()
                return True
            return False

    def heartbeat(self, token: str | None) -> bool:
        """Refresh the hold for ``token``. Returns False if it no longer holds."""
        if not token:
            return False
        with self._lock:
            if self._holder() == token:
                self._last_seen = time.monotonic()
                return True
            return False

    def release(self, token: str | None) -> None:
        """Release control if ``token`` is the current holder."""
        with self._lock:
            if self._token == token:
                self._token = None

    def is_holder(self, token: str | None) -> bool:
        """Return True if ``token`` currently holds control."""
        if not token:
            return False
        with self._lock:
            return self._holder() == token

    def in_use(self) -> bool:
        """Return True if any (non-expired) client holds control."""
        with self._lock:
            return self._holder() is not None

    def reset(self) -> None:
        """Drop any current holder (used by tests)."""
        with self._lock:
            self._token = None
            self._last_seen = 0.0


# Process-wide singleton shared by routes and the OLED display.
lock = ControlLock()
