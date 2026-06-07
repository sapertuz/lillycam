"""Test the SSD1306 OLED display.

Runs through several screens:
  1. Basic I2C connectivity check (3 static screens)
  2. Status layout (IP / URL / last dispense) as shown in the real app

Usage:
    python examples/test_oled.py
    python examples/test_oled.py --address 0x3D  # if your module uses 0x3D
"""

import argparse
import sys
import time

from lillycam import pins
from lillycam.display import Display


def main() -> None:
    parser = argparse.ArgumentParser(description="Test SSD1306 OLED display")
    parser.add_argument("--address", default="0x3C", help="I2C address (default: 0x3C)")
    args = parser.parse_args()

    print(f"Connecting to SSD1306 at I2C {args.address}")

    try:
        d = Display()
    except Exception as exc:
        print(f"ERROR: Could not initialize display: {exc}")
        print("Check: I2C enabled? sudo raspi-config -> Interface Options -> I2C")
        print("Check: sudo i2cdetect -y 1  (should show device at 0x3c or 0x3d)")
        sys.exit(1)

    try:
        # --- 1. Basic connectivity ---
        print("\n[1/2] Basic screens (2s each)...")
        d.show_message("LillyCam")
        time.sleep(2)
        d.show_message(f"SDA=GPIO {pins.OLED_SDA}")
        time.sleep(2)
        d.show_message("128x32 OK")
        time.sleep(2)

        # --- 2. Status layout (as used in the real app) ---
        print("[2/2] Status layout...")
        d.show_status()
        time.sleep(4)

        d.clear()
        print("\nPASS: OLED test complete")

    finally:
        d.close()


if __name__ == "__main__":
    main()
