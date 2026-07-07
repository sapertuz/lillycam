"""Entry point for LillyCam: python -m lillycam

Initializes all hardware, starts the Flask web server, and
keeps the OLED display updated. Shuts down cleanly on Ctrl-C.
"""

import logging
import signal
import sys

from lillycam import config
from lillycam.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    camera = stepper = servo = display = None

    try:
        log.info("LillyCam starting up...")

        from lillycam.display import Display
        display = Display()
        display.show_message("LillyCam starting...")

        from lillycam.camera import Camera
        camera = Camera()
        # Camera stays off at boot by default (privacy); turn it on from the web UI.
        if config.CAMERA_AUTOSTART:
            try:
                camera.start_stream()
            except Exception as exc:
                log.warning("Camera not available: %s", exc)
                camera = None

        from lillycam.stepper import Stepper
        stepper = Stepper()

        from lillycam.servo import Servo
        servo = Servo()

        app = create_app(camera=camera, stepper=stepper, servo=servo, display=display)

        # Power-saver: when the last controller leaves, turn the camera off so
        # it never streams with nobody watching (single-core Pi, privacy too).
        if config.CAMERA_OFF_ON_IDLE:
            from lillycam.control import lock

            def _on_idle() -> None:
                if camera is not None and camera.is_streaming:
                    log.info("No controller connected; turning camera off")
                    camera.stop_stream()
                display.set_camera(False)

            lock.set_on_release(_on_idle)

        display.show_status(port=config.FLASK_PORT)
        display.set_camera(camera is not None and camera.is_streaming)
        log.info("Ready. Listening on %s:%d", config.FLASK_HOST, config.FLASK_PORT)

        ssl_context = None
        if config.TAILSCALE_CERT and config.TAILSCALE_KEY:
            ssl_context = (config.TAILSCALE_CERT, config.TAILSCALE_KEY)
            log.info("HTTPS enabled with cert: %s", config.TAILSCALE_CERT)

        app.run(
            host=config.FLASK_HOST,
            port=config.FLASK_PORT,
            debug=config.FLASK_DEBUG,
            use_reloader=False,  # reloader conflicts with GPIO and camera
            threaded=True,
            ssl_context=ssl_context,
        )

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        if display:
            display.show_message("Shutting down...")
        for hw in (camera, stepper, servo, display):
            if hw is not None:
                try:
                    hw.close()
                except Exception as exc:
                    log.warning("Error closing %s: %s", hw.__class__.__name__, exc)
        log.info("Goodbye")


if __name__ == "__main__":
    main()
