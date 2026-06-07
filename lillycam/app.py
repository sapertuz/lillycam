"""Flask application factory for LillyCam.

Creates and configures the Flask app. Hardware objects are attached
to the app context so routes can access them via current_app.
"""

import logging

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

    # Attach hardware to app context
    app.camera = camera
    app.stepper = stepper
    app.servo = servo
    app.display = display

    from lillycam.web.routes import bp
    app.register_blueprint(bp)

    log.info("Flask app created")
    return app
