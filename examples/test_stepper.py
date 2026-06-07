"""Test the 28BYJ-48 stepper motor via ULN2003 driver.

Runs the stepper forward then backward by the specified number of
half-steps, then de-energizes the coils.

28BYJ-48 specs: 4096 half-steps per output shaft revolution.
  512 half-steps = 1/8 rev
  1024 half-steps = 1/4 rev
  2048 half-steps = 1/2 rev
  4096 half-steps = 1 full rev

Usage:
    python examples/test_stepper.py
    python examples/test_stepper.py --steps 512
    python examples/test_stepper.py --steps 4096 --delay 0.001
"""

import argparse
import sys
import time

import RPi.GPIO as GPIO

from lillycam import pins


# Half-step sequence for ULN2003 (IN1, IN2, IN3, IN4)
_SEQ = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)


def step(count: int, delay: float, step_idx: int) -> int:
    """Step the motor `count` half-steps. Returns updated step index."""
    direction = 1 if count >= 0 else -1
    for _ in range(abs(count)):
        step_idx = (step_idx + direction) % len(_SEQ)
        state = _SEQ[step_idx]
        for pin, val in zip(pins.STEPPER_PINS, state):
            GPIO.output(pin, val)
        time.sleep(delay)
    return step_idx


def deenergize() -> None:
    for pin in pins.STEPPER_PINS:
        GPIO.output(pin, GPIO.LOW)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test 28BYJ-48 stepper motor")
    parser.add_argument("--steps", type=int, default=512, help="Half-steps to run (default: 512 = 1/8 rev)")
    parser.add_argument("--delay", type=float, default=0.002, help="Seconds between steps (default: 0.002)")
    args = parser.parse_args()

    print(f"Stepper test: {args.steps} half-steps (fwd then rev)")
    print(f"  Pins: IN1={pins.STEPPER_IN1}, IN2={pins.STEPPER_IN2}, IN3={pins.STEPPER_IN3}, IN4={pins.STEPPER_IN4}")

    GPIO.setmode(GPIO.BCM)
    for pin in pins.STEPPER_PINS:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    try:
        print("  Forward...")
        idx = step(args.steps, args.delay, 0)
        deenergize()
        time.sleep(0.5)

        print("  Reverse...")
        step(-args.steps, args.delay, idx)
        deenergize()

        print("PASS: Stepper test complete")
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        deenergize()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
