"""Test audio round-trip: mic -> speaker.

Records from the INMP441 mic then immediately plays back through the
MAX98357A amp. This is half-duplex (record then play, not simultaneous).

Usage:
    python examples/test_audio_loopback.py
    python examples/test_audio_loopback.py --seconds 3
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Audio loopback: mic -> speaker")
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--mic-device", type=str, default="mic")
    parser.add_argument("--speaker-device", type=str, default="speaker")
    args = parser.parse_args()

    try:
        import numpy as np
        from lillycam.audio import play, record
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        sys.exit(1)

    print(f"Recording {args.seconds}s from '{args.mic_device}'... speak now!")
    try:
        data = record(seconds=args.seconds, device=args.mic_device)
    except Exception as exc:
        print(f"ERROR: Recording failed: {exc}")
        sys.exit(1)

    peak = float(abs(data).max())
    print(f"Recorded. Peak amplitude: {peak:.4f}")

    if peak < 0.0001:
        print("WARNING: Very low signal. Check mic wiring and orientation.")

    print(f"Playing back through '{args.speaker_device}'...")
    try:
        play(data, device=args.speaker_device)
    except Exception as exc:
        print(f"ERROR: Playback failed: {exc}")
        sys.exit(1)

    print("PASS: Loopback test complete")


if __name__ == "__main__":
    main()
