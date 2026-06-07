"""Test the SG90 servo on GPIO 12 using pigpio hardware PWM.

Sweeps the servo from min to max angle and back in 1-degree steps,
then cuts the PWM signal so the servo holds position silently.

Requires pigpiod running:
    sudo systemctl start pigpiod

Usage:
    python examples/test_servo.py
    python examples/test_servo.py --min 0 --max 180 --delay 0.02
    python examples/test_servo.py --angle 45   # jump to a single angle
"""

import argparse
import sys
import time

import pigpio

from lillycam import pins

_PULSE_MIN = 500   # us at 0 deg
_PULSE_MAX = 2500  # us at 180 deg


def angle_to_pulse(angle: float) -> int:
    return int(_PULSE_MIN + (angle / 180.0) * (_PULSE_MAX - _PULSE_MIN))


def move_to(pi, current: float, target: float, step_delay: float) -> float:
    """Step from current to target 1 degree at a time, then silence signal."""
    direction = 1.0 if target > current else -1.0
    while abs(target - current) >= 1.0:
        current += direction
        pi.set_servo_pulsewidth(pins.SERVO, angle_to_pulse(current))
        time.sleep(step_delay)
    current = target
    pi.set_servo_pulsewidth(pins.SERVO, angle_to_pulse(current))
    time.sleep(step_delay + 0.05)
    pi.set_servo_pulsewidth(pins.SERVO, 0)  # silence - hold by friction
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="Test SG90 servo via pigpio hardware PWM")
    parser.add_argument("--min", type=float, default=0, dest="min_angle")
    parser.add_argument("--max", type=float, default=180, dest="max_angle")
    parser.add_argument("--delay", type=float, default=0.02,
                        help="Seconds per 1-degree step (default: 0.02 = ~50 deg/sec)")
    parser.add_argument("--angle", type=float, default=None,
                        help="Jump to a single angle and exit")
    args = parser.parse_args()

    pi = pigpio.pi()
    if not pi.connected:
        print("ERROR: Cannot connect to pigpiod.")
        print("Run: sudo systemctl start pigpiod")
        sys.exit(1)

    print(f"Servo test on GPIO {pins.SERVO} via pigpio hardware PWM")
    print("(1-deg steps, signal cut after each move)")

    # Center on startup then go silent
    angle = 90.0
    pi.set_servo_pulsewidth(pins.SERVO, angle_to_pulse(angle))
    time.sleep(0.5)
    pi.set_servo_pulsewidth(pins.SERVO, 0)
    print("  Centered at 90 deg (signal off)")

    try:
        if args.angle is not None:
            print(f"  Moving to {args.angle} deg")
            angle = move_to(pi, angle, args.angle, args.delay)
            print(f"  Arrived at {angle} deg (signal off)")
        else:
            print(f"  Sweeping to {args.min_angle} deg")
            angle = move_to(pi, angle, args.min_angle, args.delay)
            print(f"  Sweeping to {args.max_angle} deg")
            angle = move_to(pi, angle, args.max_angle, args.delay)
            print(f"  Sweeping back to {args.min_angle} deg")
            angle = move_to(pi, angle, args.min_angle, args.delay)
            print(f"  Centering at 90 deg")
            angle = move_to(pi, angle, 90.0, args.delay)

        print("PASS: Servo test complete (signal off, servo holds by friction)")
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        pi.set_servo_pulsewidth(pins.SERVO, 0)
        pi.stop()


if __name__ == "__main__":
    main()
