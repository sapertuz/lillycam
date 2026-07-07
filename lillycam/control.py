"""Single-connection control lock for LillyCam.

Only one device may control LillyCam at a time. This keeps a single MJPEG
stream consumer on the single-core Pi Zero and prevents two clients from
fighting over the servo and dispenser.

A client "holds" control by presenting a session token. The holder must send
periodic heartbeats; if they stop for CONTROL_TIMEOUT seconds (tab closed,
walked away) the slot auto-releases. A new client can force a takeover, which
bumps the previous holder to a locked screen on their next request.

When the last controller leaves (explicit release or timeout), an optional
``on_release`` callback fires once. LillyCam uses it to turn the camera off
so it never streams with nobody watching.

This module exposes a process-wide singleton, ``lock``, shared by the web
routes and the OLED display.
"""

import logging
import threading
import time
from typing import Callable

from lillycam import config

log = logging.getLogger(__name__)


class ControlLock:
    """Tracks which session token currently holds control (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._last_seen: float = 0.0
        self._on_release: Callable[[], None] | None = None

    def set_on_release(self, callback: Callable[[], None] | None) -> None:
        """Register a callback fired once when the last controller leaves."""
        self._on_release = callback

    def _expire_locked(self) -> bool:
        """Clear an expired holder. Returns True if one was just cleared.

        Caller must hold self._lock.
        """
        if self._token is not None and (time.monotonic() - self._last_seen) > config.CONTROL_TIMEOUT:
            self._token = None
            return True
        return False

    def claim(self, token: str | None, force: bool = False) -> bool:
        """Try to acquire control for ``token``.

        Granted if the slot is free, already held by this token, or ``force``
        is set (takeover). Returns True if this token now holds control. Never
        fires on_release: a granted claim always leaves a holder in place.
        """
        if not token:
            return False
        with self._lock:
            self._expire_locked()
            holder = self._token
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
            expired = self._expire_locked()
            if self._token == token:
                self._last_seen = time.monotonic()
                held = True
            else:
                held = False
        if expired:
            self._fire_release()
        return held

    def release(self, token: str | None) -> None:
        """Release control if ``token`` is the current holder."""
        released = False
        with self._lock:
            if self._token is not None and self._token == token:
                self._token = None
                released = True
        if released:
            self._fire_release()

    def is_holder(self, token: str | None) -> bool:
        """Return True if ``token`` currently holds control."""
        if not token:
            return False
        with self._lock:
            expired = self._expire_locked()
            held = self._token == token
        if expired:
            self._fire_release()
        return held

    def in_use(self) -> bool:
        """Return True if any (non-expired) client holds control."""
        with self._lock:
            expired = self._expire_locked()
            present = self._token is not None
        if expired:
            self._fire_release()
        return present

    def reset(self) -> None:
        """Drop any current holder without firing on_release (used by tests)."""
        with self._lock:
            self._token = None
            self._last_seen = 0.0

    def _fire_release(self) -> None:
        """Run the on_release callback off-thread so it never blocks the lock."""
        cb = self._on_release
        if cb is not None:
            threading.Thread(target=self._safe_release, args=(cb,), daemon=True).start()

    @staticmethod
    def _safe_release(cb: Callable[[], None]) -> None:
        try:
            cb()
        except Exception as exc:  # a release hook must never crash a request/render
            log.warning("on_release callback failed: %s", exc)


# Process-wide singleton shared by routes and the OLED display.
lock = ControlLock()
