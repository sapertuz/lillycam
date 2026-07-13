"""Web Push (VAPID) support for LillyCam - experimental, opt-in.

Serves the VAPID public key, stores browser push subscriptions, and sends
notifications. State (keypair + subscriptions) lives in ``config.PUSH_STATE_DIR``
so it survives code redeploys. Requires the optional ``pywebpush`` dependency;
enable with ``PUSH_ENABLED=true`` and HTTPS (the Tailscale cert).

``send_to_all()`` is the reusable hook for real events later (presence, meow).
"""

import base64
import json
import logging
import threading

from flask import Blueprint, jsonify, request

from lillycam import config

log = logging.getLogger(__name__)

push_bp = Blueprint("push", __name__)

_lock = threading.Lock()
_vapid: dict | None = None  # {"private_pem": str, "public_key": str}
_vapid_key = None  # a py_vapid Vapid01 instance used to sign push requests


def _state_dir():
    config.PUSH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return config.PUSH_STATE_DIR


def _vapid_path():
    return _state_dir() / "vapid.json"


def _subs_path():
    return _state_dir() / "push_subscriptions.json"


def init_push() -> None:
    """Load the VAPID keypair, generating one on first run.

    Raises ImportError if pywebpush is not installed, so the app factory can
    report the misconfiguration instead of silently serving broken push.
    """
    import pywebpush  # noqa: F401  fail fast if the dependency is missing
    from py_vapid import Vapid01

    global _vapid, _vapid_key
    path = _vapid_path()
    if path.exists():
        _vapid = json.loads(path.read_text())
        log.info("Loaded VAPID keypair from %s", path)
    else:
        _vapid = _generate_vapid()
        path.write_text(json.dumps(_vapid))
        log.info("Generated new VAPID keypair at %s", path)

    # Build the signing object once. pywebpush's webpush() mishandles an inline
    # PEM string (it routes to Vapid.from_string/from_der and fails to parse it),
    # but takes a ready Vapid instance via its isinstance() fast path.
    _vapid_key = Vapid01.from_pem(_vapid["private_pem"].encode())


def _generate_vapid() -> dict:
    """Create a fresh VAPID keypair (private PEM + browser application key)."""
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01

    v = Vapid01()
    v.generate_keys()
    priv_pem = v.private_pem()
    if isinstance(priv_pem, bytes):
        priv_pem = priv_pem.decode()
    raw = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    pub = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    return {"private_pem": priv_pem, "public_key": pub}


def _load_subs() -> list:
    path = _subs_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_subs(subs: list) -> None:
    _subs_path().write_text(json.dumps(subs))


@push_bp.route("/push/vapid-public-key")
def vapid_public_key():
    """Return the VAPID application server key for the browser to subscribe with."""
    return _vapid["public_key"], 200, {"Content-Type": "text/plain"}


@push_bp.route("/push/subscribe", methods=["POST"])
def subscribe():
    """Store a browser push subscription (deduplicated by endpoint)."""
    sub = request.get_json(silent=True)
    if not sub or "endpoint" not in sub:
        return jsonify(error="invalid subscription"), 400
    with _lock:
        subs = [s for s in _load_subs() if s.get("endpoint") != sub["endpoint"]]
        subs.append(sub)
        _save_subs(subs)
    return jsonify(ok=True, count=len(subs))


@push_bp.route("/push/test", methods=["POST"])
def test_push():
    """Send a test notification to every stored subscription."""
    data = request.get_json(silent=True) or {}
    payload = {
        "title": data.get("title", "LillyCam"),
        "body": data.get("body", "Test push - Lilly says hi!"),
        "url": "/",
    }
    sent, pruned = send_to_all(payload)
    return jsonify(sent=sent, pruned=pruned)


def send_to_all(payload: dict) -> tuple[int, int]:
    """Push a payload to all stored subscriptions, pruning expired ones.

    Returns (sent, pruned). Safe to call from event code (presence, meow, etc.).
    """
    from pywebpush import WebPushException, webpush

    with _lock:
        subs = _load_subs()
    keep = []
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=_vapid_key,
                vapid_claims={"sub": config.PUSH_CONTACT},
            )
            sent += 1
            keep.append(sub)
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):  # gone: the browser dropped this subscription
                log.info("Pruning expired push subscription")
            else:  # transient failure: keep the subscription for next time
                log.warning("Push send failed (%s): %s", status, exc)
                keep.append(sub)
        except Exception as exc:  # network error etc: keep and carry on, never 500
            log.warning("Push send error: %s", exc)
            keep.append(sub)
    pruned = len(subs) - len(keep)
    if pruned:
        with _lock:
            _save_subs(keep)
    return sent, pruned
