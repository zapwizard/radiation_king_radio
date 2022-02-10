import board
import audiobusio
from microcontroller import Pin

def is_hardware_PDM(clock, data):
    try:
        p = audiobusio.PDMIn(clock, data)
        p.deinit()
        return True
    except ValueError:
        return False
    except RuntimeError:
        return True


def get_unique_pins():
    exclude = ['NEOPIXEL', 'APA102_MOSI', 'APA102_SCK']
    pins = [pin for pin in [
        getattr(board, p) for p in dir(board) if p not in exclude]
            if isinstance(pin, Pin)]
    unique = []
    for p in pins:
        if p not in unique:
            unique.append(p)
    return unique


for clock_pin in get_unique_pins():
    for data_pin in get_unique_pins():
        if clock_pin is data_pin:
            continue
        if is_hardware_PDM(clock_pin, data_pin):
            print("Clock pin:", clock_pin, "\t Data pin:", data_pin)
        else:
            pass
sys.exit()








#This code goes onto the Pi Pico
import time
import board
import sys
import busio
import digitalio
import analogio
import neopixel
import pwmio
import math
import keypad
import supervisor
import pico_settings
from adafruit_simplemath import map_range, constrain
import atexit
import usb_cdc

## globals:
# ADC Related:
volume_prev = 0
ADC_0_smoothed = 0
motor_angle_prev = 0
ADC_1_smoothed = 0

#Switch related:
volume_switch_state = None
tuning_switch_state = None

#Motor related:
motor_angle = 0

#NeoPIxel related:
gauge_pixel_set_time = None

#Misc
on_off_state = False
pi_state = False
led_heartbeat_prev = 0
uart_heartbeat_time = 0
pi_zero_heartbeat_time = 0
usb_cdc.console.timeout = pico_settings.UART_TIMEOUT
usb_cdc.data.timeout = pico_settings.UART_TIMEOUT
uart_line = None

def receive_uart():
    global uart_line
    try:
        if usb_cdc.data.connected:
            uart_line = usb_cdc.data.readline() # Read data until "\n" or timeout
            if uart_line:

                if type(uart_line) is bytes:
                    uart_line = uart_line.decode("utf-8")  # Convert from bytes to string
                uart_line = uart_line.strip("\n")  # Strip end line
                return "".join(uart_line).split(",")  # Split into array of commands
    except Exception as e:
        print("Error, Uart:", e)

def send_uart(command_type, data1, data2 = "", data3 = "", data4 = ""):
    try:
        usb_cdc.data.write(bytes(f"{command_type},{data1},{data2},{data3},{data4},\n", "utf-8")) #if using USB serial
    except Exception as error:
        _, err, _ = sys.exc_info()
        print("UART Error: (%s)" % err, error)

def set_motor(angle, disable = False, from_uart = False):  # Set angle in degrees
    global motor_angle

    if angle != motor_angle: # if the angle changed:
        motor_angle = angle

        # Keep needle within the preset limits
        angle = constrain(angle, pico_settings.MOTOR_ANGLE_MIN, pico_settings.MOTOR_ANGLE_MAX)
        if not from_uart:
            send_uart("M", str(angle))  # Send angle up to the Pi Zero

        radian = angle * 0.0174  # Convert the angle to a radian (math below only works on radians)
        sin_radian = math.sin(radian)  # Calculate sin
        cos_radian = math.cos(radian)  # Calculate cos

        sin_coil_voltage = round(abs(sin_radian) * pico_settings.MOTOR_REF_VOLTAGE, 4)  # Calculate voltage needed on coil.
        sin_coil_pwm = round(map_range(sin_coil_voltage, 0, pico_settings.MOTOR_REF_VOLTAGE, 0, pico_settings.PWM_MAX_VALUE)) # Determine PWM output

        cos_coil_voltage = round(abs(cos_radian) * pico_settings.MOTOR_REF_VOLTAGE, 4)  # Calculate voltage need on coil.
        cos_coil_pwm = round(map_range(cos_coil_voltage, 0, pico_settings.MOTOR_REF_VOLTAGE, 0, pico_settings.PWM_MAX_VALUE)) # Determine PWM output

        #print("Angle:",angle, "\tSinV:", sin_coil_voltage, "\tSinPWM:", sin_coil_pwm, "\tCosV", cos_coil_voltage, "\tCosPWM=",cos_coil_pwm)

        # Change the polarity of the coil depending on the sign of the voltage level
        if sin_radian <= 0:
            pico_settings.SIN_PWM.duty_cycle = sin_coil_pwm
            if pico_settings.SIN_DIRECTION:
                pico_settings.SIN_POS.value = True
                pico_settings.SIN_NEG.value = False
            else:
                pico_settings.SIN_POS.value = False
                pico_settings.SIN_NEG.value = True
        else:
            pico_settings.SIN_PWM.duty_cycle = sin_coil_pwm
            pico_settings.SIN_POS.value = False
            pico_settings.SIN_NEG.value = True
        if cos_radian <= 0:
            pico_settings.COS_PWM.duty_cycle = cos_coil_pwm
            if pico_settings.COS_DIRECTION:
                pico_settings.COS_POS.value = True
                pico_settings.COS_NEG.value = False
            else:
                pico_settings.COS_POS.value = False
                pico_settings.COS_NEG.value = True
        else:
            pico_settings.COS_PWM.duty_cycle = cos_coil_pwm
            if pico_settings.COS_DIRECTION:
                pico_settings.COS_POS.value = False
                pico_settings.COS_NEG.value = True
            else:
                pico_settings.COS_POS.value = True
                pico_settings.COS_NEG.value = False

    if disable:
        time.sleep(0.5)
        pico_settings.SIN_PWM.duty_cycle = 0
        pico_settings.SIN_POS.value = False
        pico_settings.SIN_NEG.value = False
        pico_settings.COS_PWM.duty_cycle = 0
        pico_settings.COS_POS.value = False
        pico_settings.COS_NEG.value = False

def test_motor():
    set_motor(0)
    time.sleep(1)
    for angle in range(pico_settings.MOTOR_ANGLE_MIN, pico_settings.MOTOR_ANGLE_MAX):
        set_motor(angle)
        time.sleep(0.05)
    set_motor(pico_settings.MOTOR_ANGLE_MIN)
    time.sleep(3)
    set_motor(pico_settings.MOTOR_MID_POINT)
    time.sleep(3)
    set_motor(pico_settings.MOTOR_ANGLE_MAX)
    time.sleep(3)


def blink_led():
    pico_settings.led.value = not pico_settings.led.value

def check_buttons():
    button_event = pico_settings.buttons.events.get()
    time_ticks = supervisor.ticks_ms()
    for button_num, press_time in enumerate(pico_settings.BUTTON_PRESS_TIME):
        if press_time and time_ticks > press_time + pico_settings.BUTTON_LONG_PRESS:
            #print("Debug: Button", button_num, "held for", button_long_press, "ms", time_ticks)
            pico_settings.BUTTON_PRESS_TIME[button_num] = None
            pico_settings.button_held_state[button_num] = True
            return button_num, pico_settings.BUTTON_HELD

    if button_event:
        if button_event.pressed:
            #print("Debug: Button",button_event.key_number,"Pressed at",button_event.timestamp)
            pico_settings.BUTTON_PRESS_TIME[button_event.key_number] = button_event.timestamp
            return button_event.key_number, pico_settings.BUTTON_PRESSED

        if button_event.released:
            pico_settings.BUTTON_PRESS_TIME[button_event.key_number] = None
            if pico_settings.button_held_state[button_event.key_number] is True:
                #print("Debug: Button",button_event.key_number,"Released after a hold",button_event.timestamp)
                pico_settings.button_held_state[button_event.key_number] = False
            else:
                #print("Debug: Button",button_event.key_number,"Released at",button_event.timestamp)
                return button_event.key_number, pico_settings.BUTTON_RELEASED
    return None, None

def check_switches():
    switch_event = pico_settings.switches.events.get()
    if switch_event:
        if switch_event.pressed:
            return switch_event.key_number, pico_settings.SWITCH_CW
        elif switch_event.released:
            return switch_event.key_number, pico_settings.SWITCH_CCW
    return None, None

def check_adc():
    global volume_prev, motor_angle_prev
    global volume_switch_state, tuning_switch_state, ADC_1_smoothed, ADC_0_smoothed

    # Switch 0 disables ADC_0 (To allow for standby mode)
    if switch_0_state:
        ADC_0_smoothed = pico_settings.ADC_0_SMOOTHING * pico_settings.ADC_0.value + (1 - pico_settings.ADC_0_SMOOTHING) * ADC_0_smoothed
        volume = round(map_range(ADC_0_smoothed, pico_settings.ADC_Min, pico_settings.ADC_Reported_Max, 0, 1), 3)
        if volume != ADC_0_Prev_Value:
            ADC_0_Prev_Value = volume
            send_uart("V", str(volume))

    # Switch 1 disables ADC_1 (To allow for manual tuning)
    if switch_1_state:
        ADC_1_smoothed = pico_settings.ADC_1_SMOOTHING * pico_settings.ADC_1.value + (1 - pico_settings.ADC_1_SMOOTHING) * ADC_1_smoothed
        angle = round(map_range(ADC_1_smoothed, pico_settings.ADC_Min, pico_settings.ADC_Reported_Max, pico_settings.MOTOR_ANGLE_MIN,
                                pico_settings.MOTOR_ANGLE_MAX), 1)
        if angle > ADC_1_Prev_Value + pico_settings.TUNING_DEAD_ZONE or angle < ADC_1_Prev_Value - pico_settings.TUNING_DEAD_ZONE:
            ADC_1_Prev_Value = angle
            set_motor(angle)
            #print("Input: New pot driver angle:",angle)


def resume_from_standby():
    global on_off_state
    if not on_off_state:
        print("Info: Resume from standby")
        pico_settings.buttons.events.clear()
        pico_settings.switches.events.clear()
        on_off_state = True
        send_uart("P", "1")

def standby():
    global on_off_state
    if on_off_state:
        print("Info: Going into standby")
        on_off_state = False
        send_uart("P", "0")
        soft_stop()

def sweep():
    for angle in range(pico_settings.MOTOR_ANGLE_MIN, pico_settings.MOTOR_ANGLE_MAX):
        set_motor(angle)
        led_brightness = map_range(angle, pico_settings.MOTOR_ANGLE_MIN, pico_settings.MOTOR_ANGLE_MAX, 0, pico_settings.GAUGE_PIXEL_MAX_BRIGHTNESS)
        pico_settings.gauge_pixels.fill((0, 0, 0, round(led_brightness)))
        time.sleep(0.01)
    send_uart("C","Sweep Done")

def soft_stop():
    global motor_angle
    for led_brightness in range(pico_settings.GAUGE_PIXEL_MAX_BRIGHTNESS, 0, -1):
        if motor_angle < pico_settings.MOTOR_MID_POINT:
            angle = round(map_range(led_brightness, pico_settings.GAUGE_PIXEL_MAX_BRIGHTNESS, 0, motor_angle, pico_settings.MOTOR_MID_POINT), 1)
        else:
            angle = round(map_range(led_brightness, 0, pico_settings.GAUGE_PIXEL_MAX_BRIGHTNESS, pico_settings.MOTOR_MID_POINT, motor_angle), 1)
        set_motor(angle)
        pico_settings.gauge_pixels.fill((0, 0, 0, led_brightness))
        time.sleep(0.01)
    pico_settings.gauge_pixels.fill((0, 0, 0, 0))
    set_motor(pico_settings.MOTOR_MID_POINT, disable = True)

def set_pixel(pixel=None):
    global gauge_pixel_set_time
    if pixel is None:
        pico_settings.gauge_pixels.fill((0, 0, 0, pico_settings.GAUGE_PIXEL_MAX_BRIGHTNESS))
    else:
        pico_settings.gauge_pixels.fill((0, 0, 0, round(pico_settings.GAUGE_PIXEL_MAX_BRIGHTNESS / 8)))
        pico_settings.gauge_pixels[pixel] = (0, 0, 0, 255)
        neopixel_set_time = time.time()



def wait_for_pi():
    global pi_state, pi_zero_heartbeat_time, uart_heartbeat_time
    print("Info: Waiting for pi zero heartbeat")
    while not pi_state:
        blink_led()
        uart_message = receive_uart()
        if uart_message:
            #print("Pico: UART echo:",uart_message)
            try:
                if uart_message[0] == "H":
                    if uart_message[1] and len(uart_message) > 1:
                        if uart_message[1] == "Zero":
                            pi_state = True
                            pi_zero_heartbeat_time = time.time()
                            print("From Zero: Pi Zero Heartbeat received")
            except Exception as error:
                print("Error: Uart,", error)
        time.sleep(0.1)


def buttons():
    button_number, button_event_type = check_buttons()
    if button_event_type == pico_settings.BUTTON_RELEASED:
        if button_number == 0:
            print("Event: Released 0, Rewind")
            send_uart("B", "1", "0")

        elif button_number == 1:
            print("Event: Released 1, Previous band")
            send_uart("B", "1", "1")

        elif button_number == 2:
            print("Event: Released 2, Play/Pause")
            send_uart("B", "1", "2")

        elif button_number == 3:
            print("Event: Released 3, Next Band")
            send_uart("B", "1", "3")
        elif button_number == 4:
            print("Event: Released 4, Fast Forward")
            send_uart("B", "1", "4")

    if button_event_type == pico_settings.BUTTON_HELD:
        if button_number == 0:
            print("Event: Held 0, Previous song")
            send_uart("B", "2", "0")

        elif button_number == 1:
            print("Event: Held 1, Prev Station")
            send_uart("B", "2", "1")

        elif button_number == 2:
            print("Event: Held 2, Randomize Station")
            send_uart("B", "2", "2")

        elif button_number == 3:
            print("Event: Held 3, Next Station")
            send_uart("B", "2", "3")

        elif button_number == 4:
            print("Event: Held 4, Next Song")
            send_uart("B", "2", "4")

def switches():
    global volume_switch_state, tuning_switch_state
    switch_number, switch_event_type = check_switches()
    if switch_event_type is pico_settings.SWITCH_CCW:
        if switch_number == 0:
            print("Event: Switch 0, Off")
            switch_0_state = False
            standby()
        elif switch_number == 1:
            print("Event: Switch 1, Off")
            switch_1_state = False

    if switch_event_type == pico_settings.SWITCH_CW:
        if switch_number == 0:
            print("Event: Switch 0, On")
            switch_0_state = True
            resume_from_standby()
        elif switch_number == 1:
            print("Event: Switch 1, On")
            switch_1_state = True

@atexit.register
def exit_script():
    print("Exiting")
    #pico_settings.serial.Close()


print("Startup: Pi Pico Started")
# Wait for Pi Zero due to its slower boot up time
pico_settings.gauge_pixels.fill((16, 0, 0, 0))
wait_for_pi() # Wait for the Pi Zero to be up and running
pico_settings.gauge_pixels.fill((0, 12, 0, 0))
print("Startup: Waiting for on switch")
while not volume_switch_state:
    switches()
    time.sleep(0.2)
    blink_led()

switches() # Ran twice to catch tuning knob startup setting

resume_from_standby()

while True:
    now = time.time()

    if now - led_heartbeat_prev > pico_settings.LED_HEARTBEAT_INTERVAL:
            blink_led()
            led_heartbeat_prev = now

    if now - uart_heartbeat_time > pico_settings.UART_HEARTBEAT_INTERVAL:
            send_uart("H", "Pico")
            uart_heartbeat_time = now

    if now - pi_zero_heartbeat_time > pico_settings.PI_ZERO_HEARTBEAT_TIMEOUT:
        print("Timeout: Pi Zero Heartbeat not received")
        pi_zero_heartbeat_time = now
        pi_state = False
        standby()
        wait_for_pi()

    switches()
    if on_off_state:
        check_adc()
        buttons()

        if gauge_pixel_set_time:
            if now - gauge_pixel_set_time > pico_settings.NEOPIXEL_SET_TIMEOUT:
                set_pixel()
                gauge_pixel_set_time = None


    uart_message = receive_uart()

    if uart_message:
        #print("UART Received:",uart_message)
        try:
            #Power commands
            if uart_message[0] == "P":
                if len(uart_message) > 1 and uart_message[1]:
                    if on_off_state and uart_message[1] == "0":
                        standby()
                        print("From Zero: Pi Zero in standby mode")
                    elif uart_message[1] == "1":
                        resume_from_standby()
                        print("From Zero: Pi Zero resume from standby")
                    elif uart_message[1] == "On":
                        print("From Zero: Pi Zero is already running")
                        set_pixel()

            #Motor Angle
            if uart_message[0] == "M":
                #print("Message:",uart_message)
                if len(uart_message) > 1 and uart_message[1]:
                    print("From Zero: New motor angle",uart_message[1])
                    set_motor(eval(uart_message[1]),from_uart = True)

            #Other Commands
            if uart_message[0] == "C":
                if len(uart_message) > 1 and uart_message[1]:
                    if uart_message[1] == "Sweep":
                        sweep()
                    if uart_message[1] == "LED":
                        set_pixel(eval(uart_message[2]))

            # Heartbeat
            if uart_message[0] == "H":
                # print("Message:",uart_message)
                if len(uart_message) > 1 and uart_message[1]:
                    if uart_message[1] == "Zero":
                        pi_zero_heartbeat_time = now
                        pi_state = True
                        #print("From Zero: Pi Zero heartbeat received")


        except Exception as error:
            print("Uart Error:",error)

