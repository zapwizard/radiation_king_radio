#This code goes onto the Pi Pico
import board
import keypad
import digitalio
import neopixel
import pwmio
import busio
import analogio

#LED related:
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led_max_brightness = 100
led_heartbeat_interval = 1
led_heartbeat_prev = 0

# ADC related:
ADC_Min = 13
ADC_Max = 4095
ADC_Reported_Max = 65536
ADC_0 = analogio.AnalogIn(board.A0) # I recommend using a switched "Audio" or logarithmic potentiometer for the volume control
ADC_1 = analogio.AnalogIn(board.A1)  # Use a switched linear potentiometer for the tuning control.
ADC_Samples = 3

#Buttons:
buttons = keypad.Keys((board.GP10,board.GP11,board.GP12,board.GP13,board.GP14),value_when_pressed=False, pull=True)
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
switches = keypad.Keys((board.GP8,board.GP9),value_when_pressed=False, pull=True)
switch_quantity = 2
switch_ccw = 1
switch_cw = 0

#Neopixel related
#Template: pixels[0] = (RED, GREEN, BLUE) # 0-255
neopixel_order = neopixel.GRBW
neopixel_quantity = 8
pixels = neopixel.NeoPixel(board.GP15, neopixel_quantity, brightness=0.1, auto_write=True, pixel_order=neopixel_order)
pixels.fill((0,0,0,0))

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
motor_min_angle = 0
motor_max_angle = 150
motor_mid_point = (motor_max_angle - motor_min_angle) / 2

# Uart Related
uart = busio.UART(board.GP0, board.GP1, baudrate=19200, timeout=0.01)
uart_heartbeat_interval = 30
uart_heartbeat_prev = 0

# Misc
on_off_state = True