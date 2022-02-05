#This code goes onto the Pi Pico
import board
import keypad
import digitalio
import neopixel
import pwmio
import busio
import analogio
import time

# Uart Related
uart_heartbeat_interval = 3
pi_zero_heartbeat_timeout = 15 # must be greater than the heartbeat interval on pi zero
uart_timeout = 0.01


#LED related:
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led_heartbeat_interval = 1


#Neopixel related
#Template: pixels[0] = (RED, GREEN, BLUE, WHITE) # 0-255
neopixel_set_timeout = 1 # Amount of time a LED still stay on before resetting
neopixel_range = 255 # Number of steps during fade on/off

gauge_neopixel_order = neopixel.GRBW
gauge_pixel_qty = 8
gauge_pixel_color = (160, 32, 0, 38) # Use to alter the default color
gauge_pixel_max_brightness = 0.3 # Sets the entire strip max brightness
gauge_pixels = neopixel.NeoPixel(board.GP15, gauge_pixel_qty, brightness=gauge_pixel_max_brightness, auto_write=True, pixel_order=gauge_neopixel_order)
gauge_pixels.fill((0, 0, 0, 0))

aux_neopixel_order = neopixel.GRBW
aux_pixel_qty = 5
aux_pixel_color = (160, 16, 0, 0) # Use to alter the default color
aux_pixel_max_brightness = 1 # Sets the entire strip max brightness
aux_pixels = neopixel.NeoPixel(board.GP6, aux_pixel_qty, brightness=aux_pixel_max_brightness, auto_write=True, pixel_order=aux_neopixel_order)
aux_pixels.fill((0, 0, 0, 0))


# ADC related:
ADC_0_Min = 1024 # Deliberately high to allow for self-calibration
ADC_0_Max = 2048 # Deliberately low to allow for self-calibration
ADC_1_Min = 1024 # Deliberately high to allow for self-calibration
ADC_1_Max = 2048 # Deliberately low to allow for self-calibration
ADC_0 = analogio.AnalogIn(board.A0) # I recommend using a switched "Audio" or logarithmic potentiometer for the volume control
ADC_1 = analogio.AnalogIn(board.A1)  # Use a switched linear potentiometer for the tuning control.
ADC_0_Smoothing = 0.8  # Float between 0 and 1. Lower means more smoothing
ADC_1_Smoothing = 0.08  # Float between 0 and 1. Lower means more smoothing
angle_dead_zone = 0.6 # Float angle, angle has to change by more than this before the needle move. Numbers great than 1 make for jumpy needle movement.


#Buttons:
buttons = keypad.Keys((board.GP10,board.GP11,board.GP12,board.GP13,board.GP14),value_when_pressed=False, pull=True, interval=0.05)
button_quantity = 5
button_short_press = 60
button_long_press = 2000
button_press_time = [None] * button_quantity
button_release_time = [None] * button_quantity
button_released = 0
button_pressed = 1
button_held = 2
button_state = [None]* button_quantity
button_number = None
button_held_state= [False] * button_quantity
button_event_type = None


#Switches:
switches = keypad.Keys((board.GP8,board.GP9),value_when_pressed=False, pull=True, interval=0.1)
switch_quantity = 2
switch_ccw = True # Invert if your switch behavior seems backwards
switch_cw = not switch_ccw


#Motor controller related
pwm_frequency = 50000
SIN_PWM = pwmio.PWMOut(board.GP21, duty_cycle=0, frequency=pwm_frequency, variable_frequency=False)
SIN_POS = digitalio.DigitalInOut(board.GP19)
SIN_POS.direction = digitalio.Direction.OUTPUT
SIN_NEG = digitalio.DigitalInOut(board.GP18)
SIN_NEG.direction = digitalio.Direction.OUTPUT
COS_PWM = pwmio.PWMOut(board.GP20, duty_cycle=0, frequency=pwm_frequency, variable_frequency=False)
COS_POS = digitalio.DigitalInOut(board.GP17)
COS_POS.direction = digitalio.Direction.OUTPUT
COS_NEG = digitalio.DigitalInOut(board.GP16)
COS_NEG.direction = digitalio.Direction.OUTPUT
SIN_DIRECTION = False
COS_DIRECTION = False
motor_sin = None
motor_cos = None
motor_direction = None
pwm_max_value = 65535 # 65535 max
motor_ref_voltage = 3.3
motor_min_angle = 14 # This must match the settings on the Zero
motor_max_angle = 168
motor_mid_point = (motor_max_angle - motor_min_angle) / 2 + 15
motor_range = motor_max_angle - motor_min_angle

