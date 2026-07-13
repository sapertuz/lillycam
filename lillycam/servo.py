"""Servo control for LillyCam base rotation.

Controls an SG90 servo on `GPIO 12` using the kernel's hardware PWM
(via rpi-hardware-pwm). Hardware PWM gives jitter-free pulses regardless of
CPU load, with no background daemon. `GPIO 12` is a hardware-PWM pin (PWM
channel 0); enable it with `dtoverlay=pwm,pin=12,func=4` in config.txt.

Movement strategy: step 1 degree at a time, then set the duty cycle to 0 to
silence the signal. The servo holds position by friction with no holding
current - same principle as de-energizing the stepper after a dispense.

Angle range: 0-180 degrees. Default resting position: 90 degrees (center).
Pulse range: 500us (0 deg) to 2500us (180 deg) - standard SG90 range, which at
50Hz (20ms period) is 2.5%-12.5% duty cycle.
"""

import logging
import time

from rpi_hardware_pwm import HardwarePWM

from lillycam import config, pins

log = logging.getLogger(__name__)

_PULSE_MIN = 500    # microseconds at 0 degrees
_PULSE_MAX = 2500   # microseconds at 180 degrees
_STEP_DEG = 1.0     # degrees per step
_STEP_DELAY = 0.02  # seconds between steps (~50 deg/sec)


def _angle_to_duty(angle: float, freq_hz: int) -> float:
    """Convert degrees (0-180) to duty cycle percent at the given PWM frequency."""
    pulse_us = _PULSE_MIN + (angle / 180.0) * (_PULSE_MAX - _PULSE_MIN)
    period_us = 1_000_000 / freq_hz
    return pulse_us / period_us * 100.0


class Servo:
    """Controls the SG90 base-rotation servo on `GPIO 12` via kernel hardware PWM."""

    def __init__(self) -> None:
        self._freq = config.SERVO_PWM_FREQ
        try:
            self._pwm = HardwarePWM(
                pwm_channel=config.SERVO_PWM_CHANNEL,
                hz=self._freq,
                chip=config.SERVO_PWM_CHIP,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Cannot open hardware PWM for the servo on GPIO {pins.SERVO}. "
                "Enable it with 'dtoverlay=pwm,pin=12,func=4' in "
                "/boot/firmware/config.txt and reboot "
                f"(channel={config.SERVO_PWM_CHANNEL}, chip={config.SERVO_PWM_CHIP}). "
                f"Underlying error: {exc}"
            ) from exc

        self._angle = float(config.SERVO_DEFAULT_ANGLE)
        # Start centered, brief settle, then silence (servo holds by friction).
        self._pwm.start(_angle_to_duty(self._angle, self._freq))
        time.sleep(0.5)
        self._pwm.change_duty_cycle(0)
        log.info("Servo initialized at %.0f deg on GPIO %d (signal off)", self._angle, pins.SERVO)

    @property
    def angle(self) -> float:
        """Current servo angle in degrees."""
        return self._angle

    def move_to(self, angle: float, step_delay: float = _STEP_DELAY) -> None:
        """Move servo to `angle` degrees one step at a time, then cut the signal.

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
            self._pwm.change_duty_cycle(_angle_to_duty(self._angle, self._freq))
            time.sleep(step_delay)

        # Final nudge to exact target, brief settle, then silence.
        self._angle = angle
        self._pwm.change_duty_cycle(_angle_to_duty(self._angle, self._freq))
        time.sleep(step_delay + 0.05)
        self._pwm.change_duty_cycle(0)
        log.debug("Servo at %.0f deg (signal off)", self._angle)

    def center(self) -> None:
        """Return servo to center (default angle)."""
        self.move_to(config.SERVO_DEFAULT_ANGLE)

    def close(self) -> None:
        """Silence servo and release the PWM channel."""
        try:
            self._pwm.change_duty_cycle(0)
            self._pwm.stop()
        except Exception as exc:  # never let cleanup crash shutdown
            log.warning("Error closing servo PWM: %s", exc)
        log.info("Servo closed")
