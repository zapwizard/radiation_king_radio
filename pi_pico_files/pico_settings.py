#This code goes onto the Pi Pico
import board
import keypad
import digitalio
import neopixel
import pwmio
import analogio
#import busio
from ulab import numpy as np


# Uart Related
UART_HEARTBEAT_INTERVAL = 3
PI_ZERO_HEARTBEAT_TIMEOUT = 15 # must be greater than the heartbeat interval on pi zero
UART_TIMEOUT = 0.05

#LED related:
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
LED_HEARTBEAT_INTERVAL = 1

#Pi Zero Reset switch
pi_zero_reset = digitalio.DigitalInOut(board.GP22)
pi_zero_reset.direction =  digitalio.Direction.OUTPUT
pi_zero_reset.value = True
pi_zero_soft_off = digitalio.DigitalInOut(board.GP7)
pi_zero_soft_off.direction =  digitalio.Direction.OUTPUT
pi_zero_soft_off.value = True


#Neopixel related
#Template: pixels[0] = (RED, GREEN, BLUE, WHITE) # 0-255
NEOPIXEL_SET_TIMEOUT = 1 # Amount of time a LED still stay on before resetting
NEOPIXEL_RANGE = 255 # Number of steps during fade on/off
NEOPIXEL_DIM_INTERVAL = 0.005

gauge_neopixel_order = neopixel.GRBW
GAUGE_PIXEL_QTY = 8
GAUGE_PIXEL_COLOR = (160, 32, 0, 38) # Use to alter the default color
GAUGE_PIXEL_MAX_BRIGHTNESS = 0.3 # Sets the entire strip max brightness
gauge_pixels = neopixel.NeoPixel(board.GP15, GAUGE_PIXEL_QTY, brightness=GAUGE_PIXEL_MAX_BRIGHTNESS, auto_write=True, pixel_order=gauge_neopixel_order)
gauge_pixels.fill((0, 0, 0, 0))
BRIGHTNESS_SMOOTHING = 0.1

aux_neopixel_order = neopixel.GRBW
AUX_PIXEL_QTY = 5
AUX_PIXEL_COLOR = (255, 20, 0, 0) # Use to alter the default color
AUX_PIXEL_MAX_BRIGHTNESS = 1 # Sets the entire strip max brightness
aux_pixels = neopixel.NeoPixel(board.GP6, AUX_PIXEL_QTY, brightness=AUX_PIXEL_MAX_BRIGHTNESS, auto_write=True, pixel_order=aux_neopixel_order)
aux_pixels.fill((0, 0, 0, 0))


# ADC related:
ADC_0_MIN = 1024 # Deliberately high to allow for self-calibration
ADC_0_MAX = 2048 # Deliberately low to allow for self-calibration
ADC_1_MIN = 1024 # Deliberately high to allow for self-calibration
ADC_1_MAX = 2048 # Deliberately low to allow for self-calibration
ADC_0 = analogio.AnalogIn(board.A0) # I recommend using a switched "Audio" or logarithmic potentiometer for the volume control
ADC_1 = analogio.AnalogIn(board.A1)  # Use a switched linear potentiometer for the tuning control.
ADC_0_SMOOTHING = 0.8  # Float between 0 and 1. Lower means more smoothing
ADC_1_SMOOTHING = 0.6  # Float between 0 and 1. Lower means more smoothing

# Float angle, angle has to change by more than this before the needle moves.
# Numbers great than 1 make for jumpy needle movement.
# Is overwritten when digital tuning to prevent ADC noise from changing the result.
TUNING_DEAD_ZONE = 0.3 # Angle
DIGITAL_TUNING_DEAD_ZONE = 5 # This is used if the station has been digitally tuned.

#Volume settings related to remote control
VOLUME_DEAD_ZONE = 0.04 # Float 0-1
DIGITAL_VOLUME_DEAD_ZONE = 0.1
DIGITAL_VOLUME_INCREMENT = 0.13

#Buttons:
buttons = keypad.Keys((board.GP10,board.GP11,board.GP12,board.GP13,board.GP14),value_when_pressed=False, pull=True, interval=0.05)
BUTTON_QUANTITY = 5
BUTTON_SHORT_PRESS = 60 # in ms
BUTTON_LONG_PRESS = 2000 # in ms
BUTTON_PRESS_TIME = [None] * BUTTON_QUANTITY
BUTTON_RELEASE_TIME = [None] * BUTTON_QUANTITY
BUTTON_RELEASED = 0
BUTTON_PRESSED = 1
BUTTON_HELD = 2
button_state = [None] * BUTTON_QUANTITY
button_number = None
button_held_state= [False] * BUTTON_QUANTITY
button_event_type = None

#Switches:
switches = keypad.Keys((board.GP8,board.GP9),value_when_pressed=False, pull=True, interval=0.1)
SWITCH_QUANTITY = 2
SWITCH_CCW = True # Invert if your switch behavior seems backwards
SWITCH_CW = not SWITCH_CCW


#Motor controller related
PWM_FREQUENCY = 50000
SIN_PWM = pwmio.PWMOut(board.GP21, duty_cycle=0, frequency=PWM_FREQUENCY, variable_frequency=False)
SIN_POS = digitalio.DigitalInOut(board.GP19)
SIN_POS.direction = digitalio.Direction.OUTPUT
SIN_NEG = digitalio.DigitalInOut(board.GP18)
SIN_NEG.direction = digitalio.Direction.OUTPUT
COS_PWM = pwmio.PWMOut(board.GP20, duty_cycle=0, frequency=PWM_FREQUENCY, variable_frequency=False)
COS_POS = digitalio.DigitalInOut(board.GP17)
COS_POS.direction = digitalio.Direction.OUTPUT
COS_NEG = digitalio.DigitalInOut(board.GP16)
COS_NEG.direction = digitalio.Direction.OUTPUT
SIN_DIRECTION = False
COS_DIRECTION = False
motor_sin = None
motor_cos = None
motor_direction = None
PWM_MAX_VALUE = 65535 # 65535 max
MOTOR_REF_VOLTAGE = 3.3
MOTOR_ANGLE_MIN = 14 # This must match the settings on the Zero
MOTOR_ANGLE_MAX = 168
MOTOR_MID_POINT = (MOTOR_ANGLE_MAX - MOTOR_ANGLE_MIN) / 2 + 15
MOTOR_RANGE = MOTOR_ANGLE_MAX - MOTOR_ANGLE_MIN

# Ultrasonic Remote Related
REMOTE_ENABLED = True
REMOTE_THRESHOLD = 100 # Minimum signal level needed to trigger a response
REMOTE_FREQ_MIN = 30000
REMOTE_FREQ_MAX = 40000
REMOTE_SAMPLE_FREQUENCY = 82000
REMOTE_SAMPLE_SIZE = 128  # the larger this number, the greater address separation, but slower processing time
REMOTE_SAMPLE_RATE = 0.7 # Float, Seconds
REMOTE_HALF_SAMPLE_SIZE = round(REMOTE_SAMPLE_SIZE/2)
REMOTE_TOLERANCE = 2 # How close to the address do we need to get


# Spectrogram address detected when pressing buttons on the remote
REMOTE_VALID = [
7,  # Channel Lower
1,  # Volume On/Off
16,  # Sound Mute
10 # Channel Higher
]

# Filter coefficients https://fiiir.com/
FILTER = np.array([
    -0.000755852829537227,
    -0.000626265699962122,
    0.001947063654484086,
    -0.001672488617108625,
    -0.001296733451540858,
    0.005089842128538353,
    -0.004761956498194768,
    -0.002622137682319920,
    0.011912131495380505,
    -0.011579122617223657,
    -0.004291523429909216,
    0.024499575419207345,
    -0.025420068574640128,
    -0.005902080843372104,
    0.049740041414034632,
    -0.058501749624775487,
    -0.007060138842068330,
    0.137716772846327690,
    -0.269781310646196149,
    0.326732004797751885,
    -0.269781310646196149,
    0.137716772846327690,
    -0.007060138842068332,
    -0.058501749624775501,
    0.049740041414034632,
    -0.005902080843372104,
    -0.025420068574640124,
    0.024499575419207352,
    -0.004291523429909217,
    -0.011579122617223657,
    0.011912131495380512,
    -0.002622137682319922,
    -0.004761956498194771,
    0.005089842128538351,
    -0.001296733451540857,
    -0.001672488617108627,
    0.001947063654484086,
    -0.000626265699962122,
    -0.000755852829537227,
])