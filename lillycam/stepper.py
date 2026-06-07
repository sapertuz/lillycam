"""Stepper motor control for LillyCam treat dispenser.

Controls a 28BYJ-48 5V unipolar stepper motor via a ULN2003 driver board.
Uses a full-step sequence (4 states per electrical cycle) for maximum torque.

Motor specs:
  - 32 motor steps/rev (11.25 deg/step)
  - Internal gear reduction: ~64:1
  - Output shaft: 2048 full-steps/rev
  - Operating voltage: 5V, ~240mA

Default dispense: 700 full-steps (~1/3 output rev). Adjust
STEPPER_STEPS_PER_DISPENSE in .env to match your funnel geometry.
"""

import logging
import time

import RPi.GPIO as GPIO

from lillycam import config, pins

log = logging.getLogger(__name__)

# Full-step sequence for ULN2003 driver (IN1, IN2, IN3, IN4)
_STEP_SEQ: tuple[tuple[int, ...], ...] = (
    (1, 0, 0, 0),
    (0, 1, 0, 0),
    (0, 0, 1, 0),
    (0, 0, 0, 1),
)


class Stepper:
    """Controls the treat-dispensing stepper motor (28BYJ-48 via ULN2003)."""

    def __init__(self) -> None:
        GPIO.setmode(GPIO.BCM)
        for pin in pins.STEPPER_PINS:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        self._step_idx = 0
        log.info("Stepper initialized on pins %s", pins.STEPPER_PINS)

    def step(self, count: int, delay: float | None = None) -> None:
        """Advance the motor by `count` full-steps.

        Args:
            count: Number of steps. Positive = forward, negative = reverse.
            delay: Seconds between steps. Defaults to config.STEPPER_STEP_DELAY.
        """
        if delay is None:
            delay = config.STEPPER_STEP_DELAY
        direction = 1 if count >= 0 else -1
        for _ in range(abs(count)):
            self._step_idx = (self._step_idx + direction) % len(_STEP_SEQ)
            state = _STEP_SEQ[self._step_idx]
            for pin, val in zip(pins.STEPPER_PINS, state):
                GPIO.output(pin, val)
            time.sleep(delay)

    def dispense(self) -> None:
        """Run the dispenser for one configured dispense cycle, then de-energize."""
        log.info("Dispensing: %d steps", config.STEPPER_STEPS_PER_DISPENSE)
        self.step(-config.STEPPER_STEPS_PER_DISPENSE)
        self._deenergize()
        log.info("Dispense complete")

    def reverse(self) -> None:
        """Run the dispenser in reverse (unstuck), then de-energize."""
        log.info("Reversing: %d steps", config.STEPPER_STEPS_PER_DISPENSE)
        self.step(config.STEPPER_STEPS_PER_DISPENSE)
        self._deenergize()
        log.info("Reverse complete")

    def _deenergize(self) -> None:
        """De-energize all coils to reduce heat when idle."""
        for pin in pins.STEPPER_PINS:
            GPIO.output(pin, GPIO.LOW)

    def close(self) -> None:
        """De-energize coils and release GPIO resources."""
        self._deenergize()
        GPIO.cleanup(list(pins.STEPPER_PINS))
        log.info("Stepper closed")
