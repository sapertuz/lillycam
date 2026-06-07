# Raspberry Pi Setup

Target: Raspberry Pi Zero W v1.1, Raspberry Pi OS Lite (32-bit, Trixie/Debian 12), Python 3.11+.

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

```bash
git clone https://github.com/sapertuz/lillycam.git ~/lillycam
cd ~/lillycam
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

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

## 9. Configure pigpiod for I2S compatibility

pigpiod (required for servo control) uses the PCM peripheral as its DMA clock
source by default. On the Pi Zero W this conflicts with the I2S audio driver,
causing audio to play and record at half speed. The fix is a one-line override
that switches pigpiod to use the PWM peripheral for timing instead.

```bash
sudo mkdir -p /etc/systemd/system/pigpiod.service.d/
sudo cp ~/lillycam/config/pigpiod-override.conf \
    /etc/systemd/system/pigpiod.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

Verify both servo and audio work together:
```bash
.venv/bin/python examples/test_servo.py &
aplay -D speaker /tmp/lillycam_mic_test.wav
```

## 10. Install as a systemd service

```bash
sudo cp ~/lillycam/config/lillycam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lillycam
sudo systemctl start lillycam
sudo journalctl -u lillycam -f  # watch logs
```
