#This code goes onto the Pi Pico
import board
import keypad
import digitalio
import neopixel
import pwmio
import analogio
#import busio

# Uart Related
UART_HEARTBEAT_INTERVAL = 3
PI_ZERO_HEARTBEAT_TIMEOUT = 15 # must be greater than the heartbeat interval on pi zero
UART_TIMEOUT = 0.01

#LED related:
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
LED_HEARTBEAT_INTERVAL = 1

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

aux_neopixel_order = neopixel.GRBW
AUX_PIXEL_QTY = 5
AUX_PIXEL_COLOR = (160, 16, 0, 0) # Use to alter the default color
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
ADC_1_SMOOTHING = 0.2  # Float between 0 and 1. Lower means more smoothing

# Float angle, angle has to change by more than this before the needle moves.
# Numbers great than 1 make for jumpy needle movement.
# Is overwritten when digital tuning to prevent ADC noise from changing the result.
TUNING_DEAD_ZONE = 0.5 # Angle
DIGITAL_TUNING_DEAD_ZONE = 5 # This is used if the station has been digitally tuned.

#Volume settings related to remote control
VOLUME_DEAD_ZONE = 0.03 # Float 0-1
DIGITAL_VOLUME_DEAD_ZONE = 0.05
VOLUME_INCREMENT = 0.12

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
REMOTE_THRESHOLD = 60 # Minimum signal level needed to trigger response
REMOTE_FREQ_MIN = 35000
REMOTE_SAMPLE_RATE = 1
REMOTE_SAMPLE_FREQUENCY = 80000
REMOTE_SAMPLE_SIZE = 1024

# List if valid frequencies detected when pressing a button on the remote
REMOTE_FREQS = [
[39531, 39609, 39844],  # Channel Lower
[37812, 37734, 37891],  # Volume On/Off
[38750, 38828, 35547],  # Sound Mute
[38516, 38594, 35938],  # Channel Higher
]
