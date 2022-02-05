#This code goes onto the Pi Pico
import time
import sys
import math
import supervisor
from adafruit_simplemath import map_range, constrain
import atexit
import usb_cdc
import pico_settings as settings
import analogio

## globals:
# ADC Related:
ADC_0_Prev_Value = 0
ADC_0_smoothed = 0
motor_angle_prev = 0
ADC_1_smoothed = 0

#Switch related:
volume_switch_state = None
tuning_switch_state = None

#Motor related:
motor_angle = 0

#Misc
on_off_state = False
pi_state = False
led_heartbeat_prev = 0
uart_heartbeat_time = 0
pi_zero_heartbeat_time = 0
usb_cdc.console.timeout = settings.uart_timeout
usb_cdc.data.timeout = settings.uart_timeout
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

#def print(*args, **kwargs): #Disable this for local USB print debugging
#    send_uart("i",*args,**kwargs)

def set_motor(angle, disable = False, from_uart = False):  # Set angle in degrees
    global motor_angle

    if angle != motor_angle: # if the angle changed:
        motor_angle = angle

        # Keep needle within the preset limits
        angle = constrain(angle, settings.motor_min_angle, settings.motor_max_angle)
        if not from_uart:
            send_uart("M", str(angle))  # Send angle up to the Pi Zero

        radian = angle * 0.0174  # Convert the angle to a radian (math below only works on radians)
        sin_radian = math.sin(radian)  # Calculate sin
        cos_radian = math.cos(radian)  # Calculate cos

        sin_coil_voltage = round(abs(sin_radian) * settings.motor_ref_voltage, 4)  # Calculate voltage needed on coil.
        sin_coil_pwm = round(map_range(sin_coil_voltage, 0, settings.motor_ref_voltage, 0, settings.pwm_max_value)) # Determine PWM output

        cos_coil_voltage = round(abs(cos_radian) * settings.motor_ref_voltage, 4)  # Calculate voltage need on coil.
        cos_coil_pwm = round(map_range(cos_coil_voltage, 0, settings.motor_ref_voltage, 0, settings.pwm_max_value)) # Determine PWM output

        #print("Angle:",angle, "\tSinV:", sin_coil_voltage, "\tSinPWM:", sin_coil_pwm, "\tCosV", cos_coil_voltage, "\tCosPWM=",cos_coil_pwm)

        # Change the polarity of the coil depending on the sign of the voltage level
        if sin_radian <= 0:
            settings.SIN_PWM.duty_cycle = sin_coil_pwm
            if settings.SIN_DIRECTION:
                settings.SIN_POS.value = True
                settings.SIN_NEG.value = False
            else:
                settings.SIN_POS.value = False
                settings.SIN_NEG.value = True
        else:
            settings.SIN_PWM.duty_cycle = sin_coil_pwm
            settings.SIN_POS.value = False
            settings.SIN_NEG.value = True
        if cos_radian <= 0:
            settings.COS_PWM.duty_cycle = cos_coil_pwm
            if settings.COS_DIRECTION:
                settings.COS_POS.value = True
                settings.COS_NEG.value = False
            else:
                settings.COS_POS.value = False
                settings.COS_NEG.value = True
        else:
            settings.COS_PWM.duty_cycle = cos_coil_pwm
            if settings.COS_DIRECTION:
                settings.COS_POS.value = False
                settings.COS_NEG.value = True
            else:
                settings.COS_POS.value = True
                settings.COS_NEG.value = False

    if disable:
        time.sleep(0.5)
        settings.SIN_PWM.duty_cycle = 0
        settings.SIN_POS.value = False
        settings.SIN_NEG.value = False
        settings.COS_PWM.duty_cycle = 0
        settings.COS_POS.value = False
        settings.COS_NEG.value = False

def test_motor():
    set_motor(0)
    time.sleep(1)
    for angle in range(settings.motor_min_angle, settings.motor_max_angle):
        set_motor(angle)
        time.sleep(0.05)
    set_motor(settings.motor_min_angle)
    time.sleep(3)
    set_motor(settings.motor_mid_point)
    time.sleep(3)
    set_motor(settings.motor_max_angle)
    time.sleep(3)


def blink_led():
    settings.led.value = not settings.led.value

def check_buttons():
    button_event = settings.buttons.events.get()
    time_ticks = supervisor.ticks_ms()
    for button_num, press_time in enumerate(settings.button_press_time):
        if press_time and time_ticks > press_time + settings.button_long_press:
            #print("Debug: Button", button_num, "held for", button_long_press, "ms", time_ticks)
            settings.button_press_time[button_num] = None
            settings.button_held_state[button_num] = True
            return button_num, settings.button_held

    if button_event:
        if button_event.pressed:
            #print("Debug: Button",button_event.key_number,"Pressed at",button_event.timestamp)
            settings.button_press_time[button_event.key_number] = button_event.timestamp
            return button_event.key_number, settings.button_pressed

        if button_event.released:
            settings.button_press_time[button_event.key_number] = None
            if settings.button_held_state[button_event.key_number] is True:
                #print("Debug: Button",button_event.key_number,"Released after a hold",button_event.timestamp)
                settings.button_held_state[button_event.key_number] = False
            else:
                #print("Debug: Button",button_event.key_number,"Released at",button_event.timestamp)
                return button_event.key_number, settings.button_released
    return None, None

def check_switches():
    switch_event = settings.switches.events.get()
    if switch_event:
        if switch_event.pressed:
            return switch_event.key_number, settings.switch_cw
        elif switch_event.released:
            return switch_event.key_number, settings.switch_ccw
    return None, None

def check_adc():
    global volume_switch_state, tuning_switch_state

    # Switch 0 disables ADC_0 (To allow for standby mode)
    if volume_switch_state:
        check_volume_knob()
    # Switch 1 disables ADC_1 (To allow for manual tuning)
    if tuning_switch_state:
        check_tuning_knob()

def check_volume_knob():
    global ADC_0_Prev_Value, ADC_0_smoothed
    ADC_0_Value = settings.ADC_0.value

    # ADC_0 Self Calibration
    if ADC_0_Value < settings.ADC_0_Min: settings.ADC_0_Min = ADC_0_Value
    if ADC_0_Value > settings.ADC_0_Max: settings.ADC_0_Max = ADC_0_Value

    ADC_0_smoothed = settings.ADC_0_Smoothing * ADC_0_Value + (1 - settings.ADC_0_Smoothing) * ADC_0_smoothed
    volume = round(map_range(ADC_0_smoothed, settings.ADC_0_Min, settings.ADC_0_Max, 0, 1), 3)
    if volume != ADC_0_Prev_Value:
        ADC_0_Prev_Value = volume
        send_uart("V", str(ADC_0_Prev_Value))
                #print("Volume:",str(volume), ADC_0_smoothed, settings.ADC_0.value)


def check_tuning_knob():
    global motor_angle_prev, ADC_1_smoothed
    ADC_1_Value = settings.ADC_1.value

    #ADC_1 Self Calibration
    if ADC_1_Value < settings.ADC_1_Min: settings.ADC_1_Min = ADC_1_Value
    if ADC_1_Value > settings.ADC_1_Max: settings.ADC_1_Max = ADC_1_Value

    ADC_1_smoothed = settings.ADC_1_Smoothing * ADC_1_Value + (1 - settings.ADC_1_Smoothing) * ADC_1_smoothed
    angle = round(map_range(ADC_1_smoothed, settings.ADC_1_Min, settings.ADC_1_Max, settings.motor_min_angle,
                            settings.motor_max_angle), 1)
    if angle > motor_angle_prev + settings.angle_dead_zone or angle < motor_angle_prev - settings.angle_dead_zone:
        motor_angle_prev = angle
        set_motor(motor_angle_prev)


def resume_from_standby():
    global on_off_state
    if not on_off_state:
        print("Info: Resume from standby")
        settings.buttons.events.clear()
        settings.switches.events.clear()
        on_off_state = True
        send_uart("P", "1")

def standby():
    global on_off_state
    if on_off_state:
        print("Info: Going into standby")
        on_off_state = False
        send_uart("P", "0")
        soft_stop()

def sweep(restore_angle):
    set_pixels(off=True)
    for brightness in range(settings.neopixel_range):
        angle = map_range(brightness, 0, settings.neopixel_range, settings.motor_min_angle, settings.motor_max_angle)
        set_motor(angle)
        set_pixels(brightness / settings.neopixel_range)
        #print("Debug: sweep:", angle, brightness)
        #time.sleep(0.01)
    if restore_angle:
        set_motor(restore_angle)

def soft_stop():
    global motor_angle

    if motor_angle < settings.motor_mid_point:
        for angle in range(round(motor_angle), round(settings.motor_mid_point)):
            set_motor(angle)
            time.sleep(0.005)
    else:
        for angle in range(round(motor_angle), round(settings.motor_mid_point), -1):
            set_motor(angle)
            time.sleep(0.005)
    for brightness in range(settings.neopixel_range, 0, -1):
        set_pixels(brightness / settings.neopixel_range)
        time.sleep(0.005)
    set_pixels(off=True)
    set_motor(settings.motor_mid_point, disable = True)


def set_pixels(brightness=None, pixel=None, off=False, channel=None):
    if off and not channel:
        settings.gauge_pixels.fill((0, 0 ,0, 0))
        settings.aux_pixels.fill((0, 0, 0, 0))
        return
    if brightness:
        gauge_color = tuple(int(x * brightness) for x in settings.gauge_pixel_color)
        aux_color = tuple(int(x * brightness) for x in settings.aux_pixel_color)
        if channel == "Gauge":
            if off:
                settings.gauge_pixels.fill((0, 0, 0, 0))

            if pixel:
                settings.gauge_pixels.fill((0, 0, 0, 0))
                settings.gauge_pixels[pixel] = gauge_color
            else:
                settings.gauge_pixels.fill(gauge_color)
        elif channel == "Aux":
            if off:
                settings.aux_pixels.fill((0, 0, 0, 0))

            if pixel:
                settings.aux_pixels.fill((0, 0, 0, 0))
                settings.aux_pixels[pixel] = aux_color
            else:
                settings.aux_pixels.fill(aux_color)
        else:
            settings.gauge_pixels.fill(gauge_color)
            settings.aux_pixels.fill(aux_color)

    else:
        settings.gauge_pixels.fill(settings.gauge_pixel_color)
        settings.aux_pixels.fill(settings.aux_pixel_color)

def wait_for_pi():
    global pi_state, pi_zero_heartbeat_time, uart_heartbeat_time
    print("Info: Waiting for pi zero heartbeat")
    while not pi_state:
        blink_led()
        usb_cdc.data.flush()
        uart_message = receive_uart()
        if uart_message:
            print("Waiting: UART echo:",uart_message)
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
    if button_event_type == settings.button_released:
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

    if button_event_type == settings.button_held:
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
    if switch_event_type is settings.switch_ccw:
        if switch_number == 0:
            print("Event: Switch 0, Off")
            volume_switch_state = False
            standby()
        elif switch_number == 1:
            print("Event: Switch 1, Off")
            tuning_switch_state = False

    if switch_event_type == settings.switch_cw:
        if switch_number == 0:
            print("Event: Switch 0, On")
            volume_switch_state = True
            resume_from_standby()
        elif switch_number == 1:
            print("Event: Switch 1, On")
            tuning_switch_state = True

@atexit.register
def exit_script():
    print("Exiting")
    #settings.serial.Close()


print("Startup: Pi Pico Started")
# Wait for Pi Zero due to its slower boot up time
settings.gauge_pixels.fill((16, 0, 0, 0))
wait_for_pi() # Wait for the Pi Zero to be up and running
settings.gauge_pixels.fill((0, 16, 0, 0))
print("Startup: Waiting for on switch")
while not volume_switch_state:
    switches()
    time.sleep(0.2)
    blink_led()

switches() # Ran twice to catch tuning knob startup setting

resume_from_standby()

while True:
    now = time.time()

    if now - led_heartbeat_prev > settings.led_heartbeat_interval:
            blink_led()
            led_heartbeat_prev = now

    if now - uart_heartbeat_time > settings.uart_heartbeat_interval:
            send_uart("H", "Pico")
            uart_heartbeat_time = now

    if now - pi_zero_heartbeat_time > settings.pi_zero_heartbeat_timeout:
        print("Timeout: Pi Zero Heartbeat not received")
        pi_zero_heartbeat_time = now
        pi_state = False
        standby()
        wait_for_pi()

    switches()
    if on_off_state:
        check_adc()
        buttons()


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
                        #set_pixels()

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
                        sweep(eval(uart_message[2]))
                    if uart_message[1] == "Gauge":
                        set_pixels(channel="Gauge", pixel=eval(uart_message[2]),brightness=eval(uart_message[3]))
                    if uart_message[1] == "Aux":
                        set_pixels(channel="Aux", pixel=eval(uart_message[2]),brightness=eval(uart_message[3]))

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


