"""Tests for the single-connection control lock (ControlLock)."""

import time

from lillycam import config
from lillycam.control import ControlLock


def test_claim_release_and_holder():
    lk = ControlLock()
    assert lk.claim("a") is True
    assert lk.in_use() is True
    assert lk.is_holder("a") is True
    assert lk.claim("b") is False  # someone else holds it
    lk.release("a")
    assert lk.in_use() is False


def test_force_takeover_bumps_previous():
    lk = ControlLock()
    lk.claim("a")
    assert lk.claim("b", force=True) is True
    assert lk.heartbeat("a") is False  # a lost control
    assert lk.is_holder("b") is True


def test_timeout_auto_releases(monkeypatch):
    lk = ControlLock()
    lk.claim("a")
    monkeypatch.setattr(config, "CONTROL_TIMEOUT", 0.0)
    time.sleep(0.01)
    assert lk.in_use() is False


def _wait_for(flag, timeout=1.0):
    """Wait briefly for an on_release callback (it runs on a daemon thread)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if flag:
            return True
        time.sleep(0.005)
    return False


def test_on_release_fires_on_explicit_release():
    lk = ControlLock()
    calls = []
    lk.set_on_release(lambda: calls.append(1))
    lk.claim("a")
    lk.release("a")
    assert _wait_for(calls) and calls == [1]


def test_on_release_fires_on_timeout(monkeypatch):
    lk = ControlLock()
    calls = []
    lk.set_on_release(lambda: calls.append(1))
    lk.claim("a")
    monkeypatch.setattr(config, "CONTROL_TIMEOUT", 0.0)
    time.sleep(0.01)
    lk.in_use()  # observing the expiry triggers the release hook
    assert _wait_for(calls) and calls == [1]


def test_on_release_not_fired_on_takeover():
    lk = ControlLock()
    calls = []
    lk.set_on_release(lambda: calls.append(1))
    lk.claim("a")
    lk.claim("b", force=True)  # still a holder afterwards, so no release
    time.sleep(0.05)
    assert calls == []
