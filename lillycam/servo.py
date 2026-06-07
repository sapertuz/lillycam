"""Servo control for LillyCam base rotation.

Controls an SG90 servo on `GPIO 12` using pigpio hardware PWM.
pigpio sends the PWM signal from a kernel-level daemon (pigpiod), which
gives jitter-free microsecond-accurate pulses regardless of CPU load.

Movement strategy: step 1 degree at a time, then set pulsewidth to 0 to
silence the signal. The servo holds position by friction with no holding
current - same principle as de-energizing the stepper after a dispense.

Requires pigpiod to be running:
    sudo systemctl enable pigpiod && sudo systemctl start pigpiod

Angle range: 0-180 degrees. Default resting position: 90 degrees (center).
Pulse range: 500us (0 deg) to 2500us (180 deg) - standard SG90 range.
"""

import logging
import time

import pigpio

from lillycam import config, pins

log = logging.getLogger(__name__)

_PULSE_MIN = 500   # microseconds at 0 degrees
_PULSE_MAX = 2500  # microseconds at 180 degrees
_STEP_DEG = 1.0    # degrees per step
_STEP_DELAY = 0.02 # seconds between steps (~50 deg/sec)


def _angle_to_pulse(angle: float) -> int:
    """Convert degrees (0-180) to pulse width in microseconds."""
    return int(_PULSE_MIN + (angle / 180.0) * (_PULSE_MAX - _PULSE_MIN))


class Servo:
    """Controls the SG90 base-rotation servo on `GPIO 12` via pigpio."""

    def __init__(self) -> None:
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError(
                "Cannot connect to pigpiod. "
                "Run: sudo systemctl start pigpiod"
            )
        # Clear any stale signal left by a previous run that was killed abruptly
        self._pi.set_servo_pulsewidth(pins.SERVO, 0)
        self._angle = float(config.SERVO_DEFAULT_ANGLE)
        # Send one pulse to center, then go silent
        self._pi.set_servo_pulsewidth(pins.SERVO, _angle_to_pulse(self._angle))
        time.sleep(0.5)
        self._pi.set_servo_pulsewidth(pins.SERVO, 0)
        log.info("Servo initialized at %.0f deg on GPIO %d (signal off)", self._angle, pins.SERVO)

    @property
    def angle(self) -> float:
        """Current servo angle in degrees."""
        return self._angle

    def move_to(self, angle: float, step_delay: float = _STEP_DELAY) -> None:
        """Move servo to `angle` degrees one step at a time, then cut signal.

        Args:
            angle: Target angle in degrees (clamped to configured min/max).
            step_delay: Seconds between each 1-degree step.
        """
        angle = max(float(config.SERVO_MIN_ANGLE), min(float(config.SERVO_MAX_ANGLE), float(angle)))
        if abs(angle - self._angle) < 0.5:
            return

        direction = 1.0 if angle > self._angle else -1.0
        while abs(angle - self._angle) >= _STEP_DEG:
            self._angle += direction * _STEP_DEG
            self._pi.set_servo_pulsewidth(pins.SERVO, _angle_to_pulse(self._angle))
            time.sleep(step_delay)

        # Final nudge to exact target, brief settle, then silence
        self._angle = angle
        self._pi.set_servo_pulsewidth(pins.SERVO, _angle_to_pulse(self._angle))
        time.sleep(step_delay + 0.05)
        self._pi.set_servo_pulsewidth(pins.SERVO, 0)
        log.debug("Servo at %.0f deg (signal off)", self._angle)

    def center(self) -> None:
        """Return servo to center (default angle)."""
        self.move_to(config.SERVO_DEFAULT_ANGLE)

    def close(self) -> None:
        """Silence servo and release pigpio connection."""
        self._pi.set_servo_pulsewidth(pins.SERVO, 0)
        self._pi.stop()
        log.info("Servo closed")
