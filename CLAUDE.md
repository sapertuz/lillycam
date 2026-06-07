# CLAUDE.md — LillyCam Project Context

## What is LillyCam?

LillyCam is a DIY automated cat treat dispenser with remote monitoring.
It remixes an existing Instructables cereal-dispenser design with significant additions:
live camera streaming, two-way audio, servo-controlled base rotation, OLED status display,
and a Flask-based web interface accessible over Tailscale VPN.

The whole project is cat-themed (not dog-themed). Decorative elements include a Popcat meme
speaker grille, cat-eye camera surround, paw-print microphone surround, and fish-shaped corner pieces.

The target audience is hobbyists who want to build something similar. The repo should be
self-contained enough that someone with the same hardware can clone it and get it running.

## Hardware Stack

- **Compute:** Raspberry Pi Zero W v1.1 (single-core BCM2835, 512MB RAM, 32-bit OS)
- **Camera:** Pi Camera v2 (IMX219) via CSI ribbon
- **Stepper:** 28BYJ-48 5V unipolar stepper via ULN2003 driver board (full-step sequence)
- **Servo:** SG90 on GPIO 12 (hardware PWM1) for base rotation
- **Mic:** INMP441 I2S MEMS (bottom-port, acoustic inlet on solder-pad side)
- **Speaker:** MAX98357A I2S amp + 25×35mm 4Ω 3W speaker
- **Display:** SSD1306 0.91" OLED via I2C
- **Connectivity:** Flask web server, Tailscale VPN, USB gadget Ethernet for headless SSH

## GPIO Pin Assignments (conflict-free, finalized)

```
                    Pi Zero W — 40-Pin Header
                    ========================

                      (USB/power end of board)

             Pin 1  [3V3 ] [5V  ]  Pin 2      5V power in
    OLED SDA Pin 3  [SDA ] [5V  ]  Pin 4      5V power in
    OLED SCL Pin 5  [SCL ] [GND ]  Pin 6
             Pin 7  [GP04] [TX  ]  Pin 8      UART (reserved)
             Pin 9  [GND ] [RX  ]  Pin 10     UART (reserved)
  Step. IN1 Pin 11  [GP17] [GP18]  Pin 12     I2S BCLK
  Step. IN2 Pin 13  [GP27] [GND ]  Pin 14
  Step. IN3 Pin 15  [GP22] [GP23]  Pin 16     Step. IN4
             Pin 17  [3V3 ] [GP24]  Pin 18     (free)
             Pin 19  [GP10] [GND ]  Pin 20
             Pin 21  [GP09] [GP25]  Pin 22     (free)
             Pin 23  [GP11] [GP08]  Pin 24     (free)
             Pin 25  [GND ] [GP07]  Pin 26     (free)
             Pin 27  [ID_SD] [ID_SC] Pin 28    HAT ID EEPROM
             Pin 29  [GP05] [GND ]  Pin 30
             Pin 31  [GP06] [GP12]  Pin 32     Servo PWM1
             Pin 33  [GP13] [GND ]  Pin 34
  I2S LRCLK Pin 35  [GP19] [GP16]  Pin 36     (free)
             Pin 37  [GP26] [GP20]  Pin 38     Mic DOUT
             Pin 39  [GND ] [GP21]  Pin 40     Amp DIN

                     (CSI camera ribbon end)
```

Summary by subsystem:
- Stepper (ULN2003): GPIO 17, 27, 22, 23 (physical 11, 13, 15, 16)
- Servo (SG90): GPIO 12 / PWM1 (physical 32) — moved from GPIO 18 to avoid I2S BCLK conflict
- I2S shared bus: BCLK=GPIO 18, LRCLK=GPIO 19
- I2S amp (MAX98357A): DIN=GPIO 21 (physical 40)
- I2S mic (INMP441): DOUT=GPIO 20 (physical 38)
- OLED (SSD1306): SDA=GPIO 2, SCL=GPIO 3 (I2C1)
- Free: GPIO 4, 5, 6, 7, 8, 9, 10, 11, 13, 16, 24, 25, 26 (10+ pins available)

## Architecture Decisions

- **MJPEG over H.264**: 640×480 @ 15fps MJPEG via picamera2/Flask. H.264 was ruled out because
  the extra complexity isn't justified for local/Tailscale use. CPU load is ~40-44%.
- **Half-duplex audio**: the Zero W can't handle full-duplex mic+speaker simultaneously.
  Walkie-talkie (push-to-talk) style.
- **OLED shows an animated cat face**: a Popcat-style cat occupies the left third (sleeps when
  the camera is off, wakes and blinks when on, "pops" its mouth on dispense/camera-on events).
  Status text (camera state, IP:port, last dispense) fills the right side. A background thread
  repaints at `OLED_FPS` (default 6, kept low for the single-core Pi). Set `OLED_ANIMATE=false`
  for static text only.
- **Camera off by default**: the stream does not auto-start at boot (privacy). It is turned on
  from the web UI (`/camera/on`), which also wakes the OLED cat and plays a chirp. Override with
  `CAMERA_AUTOSTART=true`.
- **Single-connection control lock**: only one device controls LillyCam at a time (one MJPEG
  stream consumer on the single-core Pi, and no two clients fighting over the servo/dispenser).
  A device claims control via a Flask-session token, keeps it with heartbeats, and auto-releases
  after `CONTROL_TIMEOUT` (default 15s) of silence. A second device sees a lock screen and can
  force a takeover (which bumps the previous holder). All control routes and `/stream` are guarded
  and return `423` to non-holders. The lock is a process-wide singleton in `lillycam/control.py`,
  shared by the routes and the OLED (which shows `in use` / `idle` on line 2 instead of the IP).
- **No src/ layout**: this is an appliance you clone and run, not a PyPI package. Flat layout
  with a `lillycam/` package directory at the root.
- **GPIO 18 conflict resolution**: servo uses GPIO 12 (PWM1) so GPIO 18 is free for I2S BCLK.
- **Power via GPIO 5V pins**: bypasses Pi's onboard polyfuse, so external polyfuses are required
  on the perfboard power distribution.
- **Still capture**: uses stop-capture-restart pattern (stop stream → capture full-res 3280×2464 →
  restart stream). Saves timestamped JPEGs to ~/captures/.

## Tech Stack

- Python 3.11+
- Flask (web server)
- picamera2 (camera control)
- RPi.GPIO (stepper GPIO) + pigpio (servo hardware PWM via pigpiod)
- luma.oled + luma.core (SSD1306 driver)
- smbus2 (I2C)
- sounddevice + numpy (audio I/O via ALSA/I2S)
- Tailscale (VPN, installed at OS level)

## Project Structure

```
lillycam/
├── README.md
├── LICENSE                        # Apache 2.0
├── NOTICE                         # attribution (author + Instructables source)
├── pyproject.toml                 # metadata + deps (not for PyPI, just for pip install -e .)
├── requirements.txt               # pinned deps for Pi deployment
├── .gitignore
├── .env.example                   # sample config (pins, stream resolution, etc.)
│
├── docs/
│   ├── hardware.md                # BOM, wiring diagram, GPIO pin map
│   ├── assembly.md                # physical build instructions, photos
│   ├── pi-setup.md                # OS image, WiFi, SSH, I2S overlays, ALSA config
│   └── images/                    # wiring photos, diagrams, enclosure renders
│
├── config/
│   ├── asound.conf                # ALSA config for I2S mic + amp
│   ├── config.txt.snippet         # boot/config.txt lines (dtoverlay=i2s, etc.)
│   ├── lillycam.service           # systemd unit file
│   └── pigpiod-override.conf      # systemd drop-in: pigpiod -t 0 for I2S compat
│
├── 3d-models/                     # CAD files (editable source + print meshes)
│   ├── step/                      # editable STEP (opens in any CAD tool)
│   └── stl/                       # print-ready STL meshes
│
├── examples/                      # standalone peripheral test scripts
│   ├── test_stepper.py            # spin stepper N steps, verify wiring
│   ├── test_servo.py              # sweep servo, verify range
│   ├── test_camera.py             # capture a still, save to disk
│   ├── test_stream.py             # MJPEG stream at localhost:8080
│   ├── test_oled.py               # display text on SSD1306
│   ├── test_mic.py                # record 5s of audio from INMP441
│   ├── test_speaker.py            # play a test tone through MAX98357A
│   └── test_audio_loopback.py     # mic → speaker round-trip
│
├── lillycam/                      # main application package
│   ├── __init__.py                # version string
│   ├── __main__.py                # entry point: python -m lillycam
│   ├── app.py                     # Flask app factory
│   ├── camera.py                  # picamera2 wrapper (stream + still capture)
│   ├── stepper.py                 # stepper motor control (dispense treats)
│   ├── servo.py                   # servo control (base rotation)
│   ├── audio.py                   # mic recording + speaker playback (half-duplex)
│   ├── display.py                 # SSD1306 OLED status display
│   ├── pins.py                    # GPIO pin assignments (single source of truth)
│   └── config.py                  # loads .env / defaults
│
├── lillycam/web/
│   ├── routes.py                  # Flask route handlers
│   ├── templates/
│   │   └── index.html             # main control page
│   └── static/
│       ├── style.css
│       └── app.js                 # frontend (stream viewer, PTT button, etc.)
│
└── tests/                         # unit tests (run on dev machine, mock GPIO)
    ├── conftest.py                # pytest fixtures, GPIO mocking
    ├── test_config.py
    ├── test_stepper_logic.py      # step sequencing logic, not hardware
    └── test_routes.py             # Flask test client
```

## Coding Conventions

- All GPIO pin numbers come from `lillycam/pins.py`. Never hardcode pin numbers elsewhere.
- Each `examples/` script is self-contained with `if __name__ == "__main__"` and argparse.
- Each `examples/` script imports pins from `lillycam.pins` so there's one source of truth.
- Docstrings on all public functions. Keep them short and practical.
- No em dashes in comments or docs (use parentheses for asides).
- Inline code backticks for hardware labels: `GPIO 18`, `BCLK`, `SDA`.
- Use parentheses for nested asides, not brackets: "the pure Python library (no C dependency - because we want portability)".
- Keep README sections concise. Don't over-explain things obvious to the hardware audience.
- Type hints on function signatures.
- f-strings, not .format() or % formatting.
- logging module, not print(), in the main application. print() is fine in examples/.

## Phase Plan

This project is built incrementally. Each phase should produce something testable.

**Phase 1 — Scaffold**: directory structure, pyproject.toml, requirements.txt, .gitignore,
.env.example, pins.py, config.py, skeleton README, LICENSE.

**Phase 2 — Peripheral tests (examples/)**: one script per peripheral. Order: OLED → stepper →
servo → camera still → MJPEG stream → mic → speaker → audio loopback.

**Phase 3 — Core library (lillycam/)**: extract working logic from examples into modules with
clean APIs, classes, docstrings, and cleanup/shutdown methods.

**Phase 4 — Flask web app**: app factory, routes, templates, static assets. Endpoints for
stream, capture, dispense, rotate, push-to-talk.

**Phase 5 — Integration + systemd**: __main__.py wires everything together. systemd unit for
autostart. OLED shows boot status then IP/URL once ready.

**Phase 6 — Tests + docs**: mocked-GPIO unit tests, hardware.md, assembly.md, pi-setup.md.
