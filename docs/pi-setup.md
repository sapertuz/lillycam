# Raspberry Pi Setup

Target: Raspberry Pi Zero W v1.1, Raspberry Pi OS Lite (32-bit, Trixie/Debian 12), Python 3.11+.

> **Building LillyCam Pro (Pi Zero 2 W)?** Most of these steps are the same, and the
> GPIO wiring is identical. The differences are the Camera Module 3 (autofocus) and
> possibly a 64-bit OS. Set `LILLYCAM_MODEL=pro` in step 6.

## 1. Flash OS

Use Raspberry Pi Imager. Choose **Raspberry Pi OS Lite (32-bit)**.
In the imager settings (gear icon), configure:
- Hostname: `lillycam`
- SSH: enable, use your public key
- WiFi: your network credentials
- Locale: your timezone

## 2. USB Gadget Ethernet (optional, for headless SSH without WiFi)

Add to `/boot/firmware/config.txt`:
```
dtoverlay=dwc2
```

Append to `/boot/firmware/cmdline.txt` (same line, space-separated):
```
modules-load=dwc2,g_ether
```

Then `ssh lillycam.local` over USB-C data cable.

## 3. Enable Camera

```bash
sudo raspi-config  # Interface Options -> Camera -> Enable
# or on modern Pi OS:
# camera_auto_detect=1 is the default; no action needed
```

## 4. Enable I2S Audio

Add to `/boot/firmware/config.txt`:
```
dtoverlay=i2s-mmap
dtoverlay=googlevoicehat-soundcard
```

Copy ALSA config:
```bash
sudo cp ~/lillycam/config/asound.conf /etc/asound.conf
```

Reboot and verify devices appear:
```bash
aplay -l   # should show the I2S card for playback
arecord -l # should show the I2S card for capture
```

## 5. Enable I2C (for OLED)

```bash
sudo raspi-config  # Interface Options -> I2C -> Enable
```

Verify the OLED is detected:
```bash
sudo i2cdetect -y 1  # should show 0x3c
```

## 6. Install LillyCam

picamera2 and libcamera are system libraries - install them with apt (this also
pulls in a matching numpy):
```bash
sudo apt update
sudo apt install -y python3-picamera2
```

Clone, create the venv **with `--system-site-packages`** so it can see the system
picamera2, then install the remaining Python packages:
```bash
git clone https://github.com/sapertuz/lillycam.git ~/lillycam
cd ~/lillycam
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

Create your config from the template and pick the hardware variant:
```bash
cp .env.example .env
```
Then edit `.env` and set `LILLYCAM_MODEL`:
- `standard` — Pi Zero W v1.1 + Camera Module v2 (the default)
- `pro` — Pi Zero 2 W + Camera Module 3

This selects sensible per-model defaults (stream resolution/fps, OLED animation
rate); you can still override any individual setting in `.env`. Everything else in
`.env` is optional — the defaults work out of the box (step 8 appends your HTTPS
cert paths here later).

## 7. Test peripherals

```bash
cd ~/lillycam
.venv/bin/python examples/test_oled.py
.venv/bin/python examples/test_stepper.py --steps 512
.venv/bin/python examples/test_servo.py
.venv/bin/python examples/test_camera.py
.venv/bin/python examples/test_stream.py  # then open http://lillycam.local:8080
.venv/bin/python examples/test_mic.py
.venv/bin/python examples/test_speaker.py
```

## 8. Remote access via Tailscale

[Tailscale](https://tailscale.com) gives a stable private address accessible from
any of your approved devices over an encrypted WireGuard tunnel. Only devices you
approve can connect. Normal internet traffic is unaffected (split tunneling).

```bash
# Install
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate (prints a URL — open it in a browser to approve the device)
sudo tailscale up
```

After authentication, restart LillyCam:
```bash
sudo systemctl restart lillycam
```

The OLED will show the Tailscale IP (`100.x.x.x`) and the URL automatically.

**To share with someone else:**
1. Open the Tailscale admin panel → Machines → find `lillycam` → Share
2. Send the invite link — they install Tailscale once, accept the invite, and bookmark the URL
3. Revoke access anytime from the admin panel

**Enable HTTPS (required for push-to-talk microphone):**

Browsers block microphone access on plain HTTP. Tailscale can provision a real
Let's Encrypt certificate so PTT works without browser warnings.

1. In the Tailscale admin console → DNS → enable **MagicDNS** and **HTTPS Certificates**
2. On the Pi, fetch the cert:
```bash
cd ~/lillycam
HOSTNAME=$(tailscale status --json | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))")
sudo tailscale cert $HOSTNAME
```
3. The cert files are created as root. Fix ownership so the lillycam service can read them:
```bash
sudo chown admin:admin $HOSTNAME.crt $HOSTNAME.key
```
4. Add the actual paths to `~/lillycam/.env` (replace the hostname with yours):
```bash
echo "TAILSCALE_CERT=/home/admin/lillycam/$HOSTNAME.crt" >> .env
echo "TAILSCALE_KEY=/home/admin/lillycam/$HOSTNAME.key" >> .env
```
5. Restart LillyCam and open `https://<your-tailscale-hostname>:5000`

**Auto-renew the certificate (recommended):**

Tailscale certs are Let's Encrypt certs (90-day validity) and are **not** renewed
automatically, so HTTPS silently breaks after ~3 months. Install the bundled timer
to renew on a schedule (it only reissues when near expiry, and restarts LillyCam
only if the cert actually changed):

```bash
# Set your MagicDNS name in the unit, then install and enable it:
sudo sed "s/lillycam.tailXXXXX.ts.net/$HOSTNAME/" \
  ~/lillycam/config/lillycam-cert-renew.service | sudo tee /etc/systemd/system/lillycam-cert-renew.service
sudo cp ~/lillycam/config/lillycam-cert-renew.timer /etc/systemd/system/
chmod +x ~/lillycam/config/renew-cert.sh
sudo systemctl daemon-reload
sudo systemctl enable --now lillycam-cert-renew.timer

# Verify: run it once (should say "still current"), and see the next scheduled run
sudo systemctl start lillycam-cert-renew.service
systemctl list-timers lillycam-cert-renew.timer
```

## 9. Enable hardware PWM for the servo

The servo uses the kernel's hardware PWM on `GPIO 12` (jitter-free, no daemon).
Add the PWM overlay to `/boot/firmware/config.txt` (it is also in
`config/config.txt.snippet`):
```
dtoverlay=pwm,pin=12,func=4
```

Reboot, then verify the PWM chip appears and test the servo:
```bash
ls /sys/class/pwm/                    # expect pwmchip0 (pwmchip2 on a Pi 5)
.venv/bin/python examples/test_servo.py
```

Modern Pi OS grants the `gpio` group access to `/sys/class/pwm` (via its
`99-com.rules`), so the `admin`-run service can drive it. If the servo works when
you run the test with `sudo` but not from the service, add a udev rule:
```bash
sudo tee /etc/udev/rules.d/99-pwm.rules >/dev/null <<'RULE'
SUBSYSTEM=="pwm", GROUP="gpio", MODE="0660"
RULE
sudo udevadm control --reload-rules && sudo udevadm trigger
```

On a Pi 5 the PWM chip is `pwmchip2` - set `SERVO_PWM_CHIP=2` in `.env`. Dropping
pigpiod also removes the old PCM/I2S clock conflict, so audio needs no timing workaround.

## 10. Install as a systemd service

```bash
sudo cp ~/lillycam/config/lillycam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lillycam
sudo systemctl start lillycam
sudo journalctl -u lillycam -f  # watch logs
```
