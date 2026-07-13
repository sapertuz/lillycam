"""Flask application factory for LillyCam.

Creates and configures the Flask app. Hardware objects are attached
to the app context so routes can access them via current_app.
"""

import logging
import os

from flask import Flask

log = logging.getLogger(__name__)


def create_app(camera=None, stepper=None, servo=None, display=None) -> Flask:
    """Create the Flask application.

    Args:
        camera: Camera instance (or None to disable camera routes).
        stepper: Stepper instance (or None to disable dispense routes).
        servo: Servo instance (or None to disable rotation routes).
        display: Display instance (or None to skip OLED updates).

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    # Signs the session cookie that carries each device's control token.
    # A fresh key per boot is fine: it just means clients re-claim after a restart.
    app.secret_key = os.urandom(24)

    # Attach hardware to app context
    app.camera = camera
    app.stepper = stepper
    app.servo = servo
    app.display = display

    from lillycam.web.routes import bp
    app.register_blueprint(bp)

    # Web Push is opt-in (needs pywebpush + HTTPS). Register it only when asked,
    # and degrade gracefully if the dependency is missing rather than crashing.
    from lillycam import config

    log.info("Model profile: %s", config.LILLYCAM_MODEL)

    if config.PUSH_ENABLED:
        try:
            from lillycam.web.push import init_push, push_bp

            init_push()
            app.register_blueprint(push_bp)
            log.info("Web Push enabled")
        except Exception as exc:
            log.error("PUSH_ENABLED but Web Push could not start: %s", exc)

    log.info("Flask app created")
    return app
