# Assembly Guide

_Photos and renders will be added as the build progresses._

## Enclosure Overview

The enclosure consists of:
- A cylindrical body housing the treat hopper and stepper motor
- A rotating base driven by the SG90 servo
- A front panel with camera (cat-eye surround) and microphone (paw-print surround)
- A speaker grille (Popcat design)
- Fish-shaped corner accent pieces

All panels are 3D printed. STL files are in `stl/`.

## Assembly Order

1. **Print all STL parts.** Recommended: PLA, 0.2mm layer height, 20% infill.
2. **Install stepper motor** into the hopper base. The 28BYJ-48 mounts from below
   with M3 screws. The funnel insert slides onto the output shaft.
3. **Install servo** into the base plate. The servo horn attaches to the body post.
4. **Mount Pi Zero W** to the rear panel using M2.5 standoffs.
5. **Mount OLED** to the front panel. Secure with hot glue or M2 screws.
6. **Mount camera** behind the cat-eye surround. Use the Pi Camera ribbon extension
   if the body depth requires it.
7. **Mount INMP441 mic** behind the paw-print surround. Orient acoustic inlet outward.
8. **Wire perfboard** for power distribution. See `docs/hardware.md` for the polyfuse layout.
9. **Connect all ribbons and JST connectors.**
10. **Test each peripheral** using `examples/` scripts before closing the enclosure.

## Treat Hopper

The hopper is a cylindrical tube that gravity-feeds treats down to the dispense wheel.
The dispense wheel is directly coupled to the 28BYJ-48 output shaft. One dispense
cycle (`STEPPER_STEPS_PER_DISPENSE` half-steps) rotates the wheel enough to drop
one or two treats through the exit chute. Tune the step count in `.env` to match
your treat size.

## Cable Management

Route all cables along the inner wall of the body before closing. The ribbon cable
for the Pi Camera is the most sensitive to bending - maintain at least a 10mm bend radius.
