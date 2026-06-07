"""Test the Pi Camera v2 - capture a full-resolution still.

Captures one image at full sensor resolution (3280x2464) and saves it to
~/captures/ with a timestamp filename. Also prints EXIF-like metadata.

Usage:
    python examples/test_camera.py
    python examples/test_camera.py --output /tmp/test.jpg
    python examples/test_camera.py --width 1920 --height 1080
"""

import argparse
import time
from datetime import datetime
from pathlib import Path
import sys

from picamera2 import Picamera2


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Pi Camera v2 still capture")
    parser.add_argument("--output", type=str, default=None, help="Output path (default: ~/captures/test_<timestamp>.jpg)")
    parser.add_argument("--width", type=int, default=3280)
    parser.add_argument("--height", type=int, default=2464)
    args = parser.parse_args()

    if args.output:
        out = Path(args.output)
    else:
        capture_dir = Path.home() / "captures"
        capture_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = capture_dir / f"test_{timestamp}.jpg"

    print(f"Camera test: {args.width}x{args.height} -> {out}")

    try:
        cam = Picamera2()
        cfg = cam.create_still_configuration(
            main={"size": (args.width, args.height)}
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(2)  # let AGC settle

        cam.capture_file(str(out))
        cam.close()

        size_kb = out.stat().st_size // 1024
        print(f"PASS: Saved {out} ({size_kb} KB)")
    except Exception as exc:
        print(f"ERROR: {exc}")
        print("Check: camera enabled? sudo raspi-config -> Interface Options -> Camera")
        print("Check: ribbon cable seated properly on both ends")
        sys.exit(1)


if __name__ == "__main__":
    main()
