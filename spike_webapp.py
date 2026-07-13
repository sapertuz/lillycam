"""Run just the LillyCam web UI - no hardware - for the PWA / Web Push spike.

The normal entry point (python -m lillycam) initializes the camera, stepper,
servo, OLED and audio, which pulls in picamera2 / RPi.GPIO / pigpio / etc. The
spike only needs the web layer, so this serves create_app() with every hardware
object set to None. Hardware routes return 503; the PWA install, microphone
permission and Web Push paths all work unchanged.

Dependencies (no system headers, no compiling):

    pip install flask python-dotenv pywebpush

HTTPS uses the same Tailscale cert as the real service. iOS needs a valid cert
for BOTH Web Push and microphone access, so set TAILSCALE_CERT / TAILSCALE_KEY
in .env (issue one with: sudo tailscale cert <this-board's-hostname>.ts.net).

    python spike_webapp.py
"""

import logging

from lillycam import config
from lillycam.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("spike")


def main() -> None:
    app = create_app()  # camera / stepper / servo / display all None

    ssl_context = None
    if config.TAILSCALE_CERT and config.TAILSCALE_KEY:
        ssl_context = (config.TAILSCALE_CERT, config.TAILSCALE_KEY)
        log.info("HTTPS enabled with cert: %s", config.TAILSCALE_CERT)
    else:
        log.warning(
            "No TAILSCALE_CERT/KEY set - serving plain HTTP. The Add-to-Home-Screen "
            "test still works, but iOS Web Push and the microphone need HTTPS."
        )

    log.info(
        "Spike web UI on %s:%d (hardware stubbed out)",
        config.FLASK_HOST,
        config.FLASK_PORT,
    )
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        threaded=True,
        use_reloader=False,
        ssl_context=ssl_context,
    )


if __name__ == "__main__":
    main()
