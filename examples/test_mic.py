"""Test the INMP441 I2S microphone.

Records audio for a specified duration and saves it to a WAV file.
Check the file with audacity or aplay to verify the mic is working.

Usage:
    python examples/test_mic.py
    python examples/test_mic.py --seconds 3 --output /tmp/test.wav
    python examples/test_mic.py --device mic --rate 44100
"""

import argparse
import struct
import sys
import wave
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Test INMP441 I2S microphone")
    parser.add_argument("--seconds", type=float, default=5, help="Recording duration (default: 5)")
    parser.add_argument("--output", type=str, default="/tmp/lillycam_mic_test.wav")
    parser.add_argument("--device", type=str, default="mic", help="ALSA device name (default: mic)")
    parser.add_argument("--rate", type=int, default=48000)
    parser.add_argument("--channels", type=int, default=1)
    args = parser.parse_args()

    try:
        import sounddevice as sd
        import numpy as np
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        sys.exit(1)

    print(f"Recording {args.seconds}s from device '{args.device}' at {args.rate}Hz...")
    print("(Speak into the mic now)")

    try:
        data = sd.rec(
            int(args.seconds * args.rate),
            samplerate=args.rate,
            channels=args.channels,
            dtype="float32",
            device=args.device,
            blocking=True,
        )
    except Exception as exc:
        print(f"ERROR: Recording failed: {exc}")
        print("Check: /etc/asound.conf configured? ALSA card visible with 'arecord -l'")
        print("Check: dtoverlay=i2s-mmap and dtoverlay=googlevoicehat-soundcard in config.txt")
        sys.exit(1)

    peak = float(np.abs(data).max())
    rms = float(np.sqrt(np.mean(data ** 2)))
    print(f"Peak: {peak:.4f}, RMS: {rms:.4f}")

    if peak < 0.0001:
        print("WARNING: Very low signal. Check mic orientation and wiring.")

    out = Path(args.output)
    int_data = (data * 32767).astype("int16")
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(args.channels)
        wf.setsampwidth(2)
        wf.setframerate(args.rate)
        wf.writeframes(int_data.tobytes())

    size_kb = out.stat().st_size // 1024
    print(f"PASS: Saved {out} ({size_kb} KB). Play with: aplay {out}")


if __name__ == "__main__":
    main()
