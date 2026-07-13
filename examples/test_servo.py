"""Test the SG90 servo on GPIO 12 using kernel hardware PWM (rpi-hardware-pwm).

Sweeps the servo from min to max angle and back in 1-degree steps, then cuts the
PWM signal so the servo holds position silently.

Requires the PWM overlay in /boot/firmware/config.txt (then reboot):
    dtoverlay=pwm,pin=12,func=4

Usage:
    python examples/test_servo.py
    python examples/test_servo.py --min 0 --max 180 --delay 0.02
    python examples/test_servo.py --angle 45         # jump to a single angle
    python examples/test_servo.py --chip 2           # Pi 5 uses pwmchip 2
"""

import argparse
import sys
import time

from rpi_hardware_pwm import HardwarePWM

from lillycam import pins

_PULSE_MIN = 500   # us at 0 deg
_PULSE_MAX = 2500  # us at 180 deg
_FREQ = 50         # Hz (20ms period)


def angle_to_duty(angle: float) -> float:
    pulse_us = _PULSE_MIN + (angle / 180.0) * (_PULSE_MAX - _PULSE_MIN)
    return pulse_us / (1_000_000 / _FREQ) * 100.0


def move_to(pwm, current: float, target: float, step_delay: float) -> float:
    """Step from current to target 1 degree at a time, then silence the signal."""
    direction = 1.0 if target > current else -1.0
    while abs(target - current) >= 1.0:
        current += direction
        pwm.change_duty_cycle(angle_to_duty(current))
        time.sleep(step_delay)
    current = target
    pwm.change_duty_cycle(angle_to_duty(current))
    time.sleep(step_delay + 0.05)
    pwm.change_duty_cycle(0)  # silence - hold by friction
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="Test SG90 servo via kernel hardware PWM")
    parser.add_argument("--min", type=float, default=0, dest="min_angle")
    parser.add_argument("--max", type=float, default=180, dest="max_angle")
    parser.add_argument("--delay", type=float, default=0.02,
                        help="Seconds per 1-degree step (default: 0.02 = ~50 deg/sec)")
    parser.add_argument("--angle", type=float, default=None,
                        help="Jump to a single angle and exit")
    parser.add_argument("--channel", type=int, default=0, help="PWM channel (GPIO 12 = 0)")
    parser.add_argument("--chip", type=int, default=0, help="PWM chip (0 on Pi <5, 2 on Pi 5)")
    args = parser.parse_args()

    try:
        pwm = HardwarePWM(pwm_channel=args.channel, hz=_FREQ, chip=args.chip)
    except Exception as exc:
        print(f"ERROR: cannot open hardware PWM (channel={args.channel}, chip={args.chip}): {exc}")
        print("Enable it with 'dtoverlay=pwm,pin=12,func=4' in /boot/firmware/config.txt, then reboot.")
        sys.exit(1)

    print(f"Servo test on GPIO {pins.SERVO} via kernel hardware PWM")
    print("(1-deg steps, signal cut after each move)")

    # Center on startup then go silent
    angle = 90.0
    pwm.start(angle_to_duty(angle))
    time.sleep(0.5)
    pwm.change_duty_cycle(0)
    print("  Centered at 90 deg (signal off)")

    try:
        if args.angle is not None:
            print(f"  Moving to {args.angle} deg")
            angle = move_to(pwm, angle, args.angle, args.delay)
            print(f"  Arrived at {angle} deg (signal off)")
        else:
            print(f"  Sweeping to {args.min_angle} deg")
            angle = move_to(pwm, angle, args.min_angle, args.delay)
            print(f"  Sweeping to {args.max_angle} deg")
            angle = move_to(pwm, angle, args.max_angle, args.delay)
            print(f"  Sweeping back to {args.min_angle} deg")
            angle = move_to(pwm, angle, args.min_angle, args.delay)
            print("  Centering at 90 deg")
            angle = move_to(pwm, angle, 90.0, args.delay)

        print("PASS: Servo test complete (signal off, servo holds by friction)")
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        pwm.change_duty_cycle(0)
        pwm.stop()


if __name__ == "__main__":
    main()
