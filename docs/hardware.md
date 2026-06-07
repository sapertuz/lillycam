# Hardware Reference

## Bill of Materials

| Component | Model | Qty | Notes |
|-----------|-------|-----|-------|
| Compute | Raspberry Pi Zero W v1.1 | 1 | 32-bit, BCM2835, 512MB RAM |
| Camera | Pi Camera v2 (IMX219) | 1 | CSI ribbon connector |
| Stepper motor | 28BYJ-48 5V unipolar | 1 | 64:1 gearbox, ~240mA |
| Stepper driver | ULN2003 breakout | 1 | Included with most 28BYJ-48 kits |
| Servo | SG90 | 1 | Hardware PWM on `GPIO 12` |
| Microphone | INMP441 I2S MEMS | 1 | Bottom-port, acoustic inlet on solder-pad side |
| Amplifier | MAX98357A I2S mono amp | 1 | 3W class-D |
| Speaker | 25×35mm, 4Ω, 3W | 1 | Fits Popcat grille STL |
| Display | SSD1306 0.91" OLED | 1 | 128×32, I2C address 0x3C |
| Power supply | 5V DC, 2A+ | 1 | Barrel jack |
| Polyfuse | PPTC, 1A | 1 | On Pi+peripherals branch |
| Misc | Perfboard, ribbon cables, JST connectors | — | |

## GPIO Pin Map

See pin diagram in `readme.md` or `CLAUDE.md`.

All BCM pin numbers are defined in `lillycam/pins.py`.

## Wiring Notes

### 28BYJ-48 Stepper + ULN2003

The ULN2003 breakout has a 5-pin JST connector that mates directly with the 28BYJ-48.
Connect the 4 input pins (IN1-IN4) to `GPIO 17, 27, 22, 23` respectively.
Power the ULN2003 from the same 5V rail as the Pi (shares polyfuse branch - the 28BYJ-48
draws ~240mA, which is within the 1A budget with headroom).

### INMP441 Microphone

Wire orientation matters: the acoustic inlet (hole) is on the side with solder pads,
not the component side. Mount with the inlet facing toward the sound source.

| INMP441 pin | Pi pin |
|-------------|--------|
| VDD | **3V3** (pin 1) |
| GND | GND |
| SD (DOUT) | GPIO 20 (physical 38) |
| WS (LRCLK) | GPIO 19 (physical 35) |
| SCK (BCLK) | GPIO 18 (physical 12) |
| L/R | **GND** (selects left I2S channel) |

**Important:**
- VDD must be **3.3V, not 5V**. The INMP441 absolute maximum is 3.6V; at 5V it will
  not function and may be damaged.
- L/R must be tied to GND (or 3.3V for right channel). If left floating, the mic
  does not know which I2S timeslot to use and outputs silence.
- GAIN (if present on your breakout) can be left unconnected.

### MAX98357A Amplifier

| MAX98357A pin | Pi pin |
|---------------|--------|
| VIN | 5V |
| GND | GND |
| DIN | GPIO 21 (physical 40) |
| BCLK | GPIO 18 (physical 12) |
| LRC | GPIO 19 (physical 35) |
| SD (shutdown) | Leave floating (pulled high on breakout = always on) |
| GAIN | Leave floating (15 dB, maximum hardware gain) |

GAIN options for reference: GND = 3 dB, VDD = 12 dB, floating = 15 dB.
Software gain can be adjusted via `AUDIO_PLAYBACK_GAIN` in `.env`.

### SSD1306 OLED

| OLED pin | Pi pin |
|----------|--------|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 2 (physical 3) |
| SCL | GPIO 3 (physical 5) |

I2C address: `0x3C` (most common; some modules use `0x3D`).
