"""GPIO pin assignments for LillyCam.

Single source of truth for all BCM-numbered GPIO pins.
All other modules import from here - never hardcode pin numbers elsewhere.

Pi Zero W 40-pin header, BCM numbering.
"""

# --- Stepper motor (28BYJ-48 via ULN2003 driver) ---
STEPPER_IN1 = 17  # physical pin 11
STEPPER_IN2 = 27  # physical pin 13
STEPPER_IN3 = 22  # physical pin 15
STEPPER_IN4 = 23  # physical pin 16

STEPPER_PINS = (STEPPER_IN1, STEPPER_IN2, STEPPER_IN3, STEPPER_IN4)

# --- Servo (SG90, hardware PWM1) ---
SERVO = 12  # physical pin 32 (PWM1, avoids I2S BCLK conflict on GPIO 18)

# --- I2S shared bus ---
I2S_BCLK = 18   # physical pin 12
I2S_LRCLK = 19  # physical pin 35

# --- I2S amplifier (MAX98357A) ---
AMP_DIN = 21  # physical pin 40

# --- I2S microphone (INMP441) ---
MIC_DOUT = 20  # physical pin 38

# --- OLED display (SSD1306 via I2C1) ---
OLED_SDA = 2  # physical pin 3
OLED_SCL = 3  # physical pin 5
