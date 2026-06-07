"""Test the MAX98357A I2S amplifier and speaker.

Plays an ascending C-major scale so it's easy to recognise whether
the speaker is working correctly. Each note is 0.3s with a short gap.

Usage:
    python examples/test_speaker.py
    python examples/test_speaker.py --device speaker --rate 48000
    python examples/test_speaker.py --freq 440 --seconds 2  # single tone instead
"""

import argparse
import math
import sys

import numpy as np
import sounddevice as sd


# C-major scale from C4 to C5
_SCALE_NOTES = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
_NOTE_NAMES  = ["C4",   "D4",   "E4",   "F4",   "G4",   "A4",   "B4",   "C5"]


def make_tone(freq: float, seconds: float, rate: int, volume: float = 0.6) -> np.ndarray:
    """Generate a sine wave, shaped with a short fade-in/out to avoid clicks."""
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    tone = volume * np.sin(2 * math.pi * freq * t).astype("float32")
    # 10ms fade in/out
    fade = int(rate * 0.01)
    tone[:fade] *= np.linspace(0, 1, fade)
    tone[-fade:] *= np.linspace(1, 0, fade)
    return tone


def make_stereo(mono: np.ndarray) -> np.ndarray:
    """Duplicate mono array to stereo (required by the googlevoicehat I2S driver)."""
    return np.column_stack([mono, mono])


def main() -> None:
    parser = argparse.ArgumentParser(description="Test MAX98357A I2S speaker")
    parser.add_argument("--device", type=str, default="speaker")
    parser.add_argument("--rate", type=int, default=48000)
    parser.add_argument("--volume", type=float, default=1.0, help="0.0-1.0")
    parser.add_argument("--freq", type=float, default=None,
                        help="Play a single tone at this Hz instead of the scale")
    parser.add_argument("--seconds", type=float, default=1.0,
                        help="Duration for single-tone mode")
    args = parser.parse_args()

    print(f"Speaker test on device '{args.device}' at {args.rate} Hz (stereo)")

    try:
        if args.freq is not None:
            print(f"  Playing {args.freq:.0f} Hz for {args.seconds}s")
            tone = make_stereo(make_tone(args.freq, args.seconds, args.rate, args.volume))
            sd.play(tone, samplerate=args.rate, device=args.device, blocking=True)
        else:
            print("  Playing C-major scale (C4 -> C5):")
            gap = make_stereo(np.zeros(int(args.rate * 0.05), dtype="float32"))
            for freq, name in zip(_SCALE_NOTES, _NOTE_NAMES):
                print(f"    {name} ({freq:.0f} Hz)", end="  ", flush=True)
                tone = make_stereo(make_tone(freq, 0.3, args.rate, args.volume))
                sd.play(tone, samplerate=args.rate, device=args.device, blocking=True)
                sd.play(gap, samplerate=args.rate, device=args.device, blocking=True)
            print()

        print("PASS: Speaker test complete")

    except Exception as exc:
        print(f"\nERROR: {exc}")
        print("Check: aplay -l  (I2S card should appear)")
        print("Check: /etc/asound.conf  (card name = sndrpigooglevoi)")
        sys.exit(1)


if __name__ == "__main__":
    main()
