
#This code goes onto the Pi Pico
import pico_settings as settings
import time
import sys
import math
import supervisor
from adafruit_simplemath import map_range, constrain
import atexit
import usb_cdc


## globals:
# ADC Related:
volume_prev = 0
VOLUME_ADC_smoothed = 0
volume_dead_zone = settings.VOLUME_DEAD_ZONE
volume = 0
motor_angle_prev = 0
TUNING_ADC_smoothed = 0
tuning_dead_zone = settings.TUNING_DEAD_ZONE

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
usb_cdc.console.timeout = settings.UART_TIMEOUT
usb_cdc.data.timeout = settings.UART_TIMEOUT
uart_line = None
brightness_smoothed = 0


def receive_uart():
    global uart_line
    try:
        if usb_cdc.data.connected and usb_cdc.data.in_waiting:
            available = usb_cdc.data.in_waiting
            while available:
                uart_line = usb_cdc.data.read(available)
                available = usb_cdc.data.in_waiting

            #uart_line = usb_cdc.data.readline() # Read data until "\n" or timeout. This line is blocking if there is no data in the buffer.

            if uart_line:
                #print("DEBUG: UART_LINE:", uart_line)
                if type(uart_line) is bytes:
                    uart_line = uart_line.decode("utf-8")  # Convert from bytes to string
                uart_line = uart_line.strip("\n")  # Strip end line
                return "".join(uart_line).split(",")  # Split into array of commands
    except Exception as e:
        print("ERROR: Uart:", e)

def send_uart(command_type, data1, data2 = "", data3 = "", data4 = ""):
    try:
        usb_cdc.data.write(bytes(f"{command_type},{data1},{data2},{data3},{data4},\n", "utf-8")) #if using USB serial
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("ERROR: Uart:", e)

    # To debug the Pico on the Pi Zero run: minicom -b 115200 -o -D /dev/ttyACM0
    #Comment this method out for local USB print debugging
    #if not usb_cdc.console:
        #        def print(*args, **kwargs):
        #        send_uart("I", *args, **kwargs)


def set_motor(angle, disable = False, from_uart = False):  # Set angle in degrees
    global motor_angle

    if angle != motor_angle: # if the angle changed:
        motor_angle = angle

        # Keep needle within the preset limits
        angle = constrain(angle, settings.MOTOR_ANGLE_MIN, settings.MOTOR_ANGLE_MAX)
        if not from_uart:
            send_uart("M", str(angle))  # Send angle up to the Pi Zero

        radian = angle * 0.0174  # Convert the angle to a radian (math below only works on radians)
        sin_radian = math.sin(radian)  # Calculate sin
        cos_radian = math.cos(radian)  # Calculate cos

        sin_coil_voltage = round(abs(sin_radian) * settings.MOTOR_REF_VOLTAGE, 4)  # Calculate voltage needed on coil.
        sin_coil_pwm = round(map_range(sin_coil_voltage, 0, settings.MOTOR_REF_VOLTAGE, 0, settings.PWM_MAX_VALUE)) # Determine PWM output

        cos_coil_voltage = round(abs(cos_radian) * settings.MOTOR_REF_VOLTAGE, 4)  # Calculate voltage need on coil.
        cos_coil_pwm = round(map_range(cos_coil_voltage, 0, settings.MOTOR_REF_VOLTAGE, 0, settings.PWM_MAX_VALUE)) # Determine PWM output

        #print("DEBUG: Angle:",angle, "\tSinV:", sin_coil_voltage, "\tSinPWM:", sin_coil_pwm, "\tCosV", cos_coil_voltage, "\tCosPWM=",cos_coil_pwm)

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
        time.sleep(0.2)
        settings.SIN_PWM.duty_cycle = 0
        settings.SIN_POS.value = False
        settings.SIN_NEG.value = False
        settings.COS_PWM.duty_cycle = 0
        settings.COS_POS.value = False
        settings.COS_NEG.value = False


def test_motor():
    set_motor(0)
    time.sleep(1)
    set_motor(settings.MOTOR_ANGLE_MIN)
    print("Minimum angle")
    time.sleep(3)
    for angle in range(settings.MOTOR_ANGLE_MIN, settings.MOTOR_ANGLE_MAX):
        set_motor(angle)
        blink_led()
        time.sleep(0.05)
    set_motor(settings.MOTOR_ANGLE_MAX)
    time.sleep(3)
    print("Maximum angle")
    set_motor(settings.MOTOR_MID_POINT)
    time.sleep(3)
    print("Middle angle")

def blink_led():
    settings.led.value = not settings.led.value

def get_button_states():
    button_event = settings.buttons.events.get()
    time_ticks = supervisor.ticks_ms()
    for button_num, press_time in enumerate(settings.BUTTON_PRESS_TIME):
        if press_time and time_ticks > press_time + settings.BUTTON_LONG_PRESS:
            print("DEBUG: Button", button_num, "held for", settings.BUTTON_LONG_PRESS, "ms", time_ticks)
            settings.BUTTON_PRESS_TIME[button_num] = None
            settings.button_held_state[button_num] = True
            return button_num, settings.BUTTON_HELD

    if button_event:
        if button_event.pressed:
            print("DEBUG: Button",button_event.key_number,"Pressed at",button_event.timestamp)
            settings.BUTTON_PRESS_TIME[button_event.key_number] = button_event.timestamp
            return button_event.key_number, settings.BUTTON_PRESSED

        if button_event.released:
            settings.BUTTON_PRESS_TIME[button_event.key_number] = None
            if settings.button_held_state[button_event.key_number] is True:
                print("DEBUG: Button",button_event.key_number,"Released after a hold",button_event.timestamp)
                settings.button_held_state[button_event.key_number] = False
            else:
                print("DEBUG: Button",button_event.key_number,"Released at",button_event.timestamp)
                return button_event.key_number, settings.BUTTON_RELEASED
    return None, None


def check_switches():
    switch_event = settings.switches.events.get()
    if switch_event:
        if switch_event.pressed:
            return switch_event.key_number, settings.SWITCH_CW
        elif switch_event.released:
            return switch_event.key_number, settings.SWITCH_CCW
    return None, None


def brightness_control():
    global brightness_smoothed
    settings.GAUGE_PIXEL_MAX_BRIGHTNESS = map_range(get_volume_adc(), settings.VOLUME_ADC_MIN, settings.VOLUME_ADC_MAX, 0, 1)
    brightness_smoothed = round(settings.BRIGHTNESS_SMOOTHING * settings.GAUGE_PIXEL_MAX_BRIGHTNESS + (1 - settings.BRIGHTNESS_SMOOTHING) * brightness_smoothed, 3)
    settings.gauge_pixels.brightness = brightness_smoothed
    print("DEBUG: Brightness:",brightness_smoothed)

def get_volume_adc():
    global VOLUME_ADC_smoothed
    adc_0_value = settings.VOLUME_ADC.value

    # VOLUME_ADC Self Calibration
    if adc_0_value < settings.VOLUME_ADC_MIN:
        settings.VOLUME_ADC_MIN = adc_0_value
        print("DEBUG: Calibration: New Min VOLUME_ADC value", settings.VOLUME_ADC_MIN)
    if adc_0_value > settings.VOLUME_ADC_MAX:
        settings.VOLUME_ADC_MAX = adc_0_value
        print("DEBUG: Calibration: New Max VOLUME_ADC value", settings.VOLUME_ADC_MAX)

    VOLUME_ADC_smoothed = settings.VOLUME_ADC_SMOOTHING * adc_0_value + (1 - settings.VOLUME_ADC_SMOOTHING) * VOLUME_ADC_smoothed
    return VOLUME_ADC_smoothed


def get_tuning_adc():
    global TUNING_ADC_smoothed
    turning_adc_value = settings.TUNING_ADC.value

    #TUNING_ADC Self Calibration
    if turning_adc_value < settings.TUNING_ADC_MIN:
        settings.TUNING_ADC_MIN = turning_adc_value
        print("DEBUG: Calibration: New Min TUNING_ADC value", settings.TUNING_ADC_MIN)
    if turning_adc_value > settings.TUNING_ADC_MAX:
        settings.TUNING_ADC_MAX = turning_adc_value
        print("DEBUG: Calibration: New Max TUNING_ADC value", settings.TUNING_ADC_MAX)

    TUNING_ADC_smoothed = settings.TUNING_ADC_SMOOTHING * turning_adc_value + (1 - settings.TUNING_ADC_SMOOTHING) * TUNING_ADC_smoothed
    return TUNING_ADC_smoothed


def check_volume_knob():
    global volume_prev, volume_dead_zone, volume

    volume_setting = round(map_range(get_volume_adc(),settings.VOLUME_ADC_MIN, settings.VOLUME_ADC_MAX,0, 1), 3)

    if volume_setting > volume_prev + volume_dead_zone or volume_setting < volume_prev - volume_dead_zone:
        volume_prev = volume_setting
        volume = volume_setting
        send_uart("V", str(volume))
        volume_dead_zone = settings.VOLUME_DEAD_ZONE
        print("DEBUG Volume:",volume, VOLUME_ADC_smoothed, settings.VOLUME_ADC.value)


def check_tuning_knob():
    global motor_angle_prev, tuning_dead_zone
    angle = round(map_range(get_tuning_adc(),settings.TUNING_ADC_MIN, settings.TUNING_ADC_MAX,settings.MOTOR_ANGLE_MIN, settings.MOTOR_ANGLE_MAX), 1)
    if angle > motor_angle_prev + tuning_dead_zone or angle < motor_angle_prev - tuning_dead_zone:
        motor_angle_prev = angle
        set_motor(angle)
        tuning_dead_zone = settings.TUNING_DEAD_ZONE # Reset the deadzone upon manual knob movement.
        #print("DEBUG: Tuning:",angle)


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
    for brightness in range(settings.NEOPIXEL_RANGE):
        angle = map_range(brightness, 0, settings.NEOPIXEL_RANGE, settings.MOTOR_ANGLE_MIN, settings.MOTOR_ANGLE_MAX)
        set_motor(angle)
        set_pixels(brightness / settings.NEOPIXEL_RANGE)
        #print("DEBUG: sweep:", angle, brightness)
        time.sleep(0.01)
    if restore_angle:
        time.sleep(0.2)
        print("Sweep: restore_angle=", restore_angle)
        set_motor(restore_angle)


def soft_stop():
    global motor_angle

    if motor_angle < settings.MOTOR_MID_POINT:
        for angle in range(round(motor_angle), round(settings.MOTOR_MID_POINT)):
            set_motor(angle)
            time.sleep(settings.NEOPIXEL_DIM_INTERVAL)
    else:
        for angle in range(round(motor_angle), round(settings.MOTOR_MID_POINT), -1):
            set_motor(angle)
            time.sleep(settings.NEOPIXEL_DIM_INTERVAL)
    for brightness in range(settings.NEOPIXEL_RANGE, 0, -1):
        set_pixels(brightness / settings.NEOPIXEL_RANGE)
        time.sleep(settings.NEOPIXEL_DIM_INTERVAL)
    set_pixels(off=True)
    set_motor(settings.MOTOR_MID_POINT, disable = True)


def set_pixels(brightness=None, pixel=None, off=False, channel=None):
    if off and not channel:
        settings.gauge_pixels.fill((0, 0 ,0, 0))
        settings.aux_pixels.fill((0, 0, 0, 0))
        return
    if brightness:
        gauge_color = tuple(int(x * brightness) for x in settings.GAUGE_PIXEL_COLOR)
        aux_color = tuple(int(x * brightness) for x in settings.AUX_PIXEL_COLOR)
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
        settings.gauge_pixels.fill(settings.GAUGE_PIXEL_COLOR)
        settings.aux_pixels.fill(settings.AUX_PIXEL_COLOR)

def wait_for_pi():
    global pi_state, pi_zero_heartbeat_time, uart_heartbeat_time, on_off_state
    print("Info: Waiting for pi zero heartbeat")
    on_off_state = False
    # Wait for Pi Zero due to its slower boot up time
    while not pi_state:
        if supervisor.runtime.usb_connected:
            settings.gauge_pixels.fill((32, 32, 0, 0))
        else:
            settings.gauge_pixels.fill((32, 0, 0, 0))
        blink_led()
        usb_cdc.data.flush()
        uart_message = receive_uart()
        if uart_message:
            print("Waiting: UART echo:",uart_message)
            try:
                if (
                    uart_message[0] == "H"
                    and uart_message[1]
                    and len(uart_message) > 1
                    and uart_message[1] == "Zero"
                ):
                    print("From Zero: Pi Zero Heartbeat received")
                    pi_state = True
                    pi_zero_heartbeat_time = time.time()
            except Exception as error:
                print("Error: Uart,", error)
    handle_buttons()
    time.sleep(0.1)

def wait_for_on_switch():
    settings.gauge_pixels.fill((0, 16, 0, 0))
    print("Startup: Waiting for on switch")
    while not volume_switch_state:
        handle_switches()
        handle_buttons()
        time.sleep(0.2)
        blink_led()

def handle_buttons():
    global on_off_state, pi_state
    button_number, button_event_type = get_button_states()

    if button_event_type == settings.BUTTON_RELEASED and on_off_state:
        if button_number == 0:
            print("EVENT: Released 0, Rewind")
            send_uart("B", "1", "0")
        elif button_number == 1:
            print("EVENT: Released 1, Previous station")
            send_uart("B", "1", "1")
        elif button_number == 2:
            print("EVENT: Released 2, Play/Pause")
            send_uart("B", "1", "2")
        elif button_number == 3:
            print("EVENT: Released 3, Next station")
            send_uart("B", "1", "3")
        elif button_number == 4:
            print("EVENT: Released 4, Fast Forward")
            send_uart("B", "1", "4")

    if button_event_type == settings.BUTTON_HELD:
        if button_number == 0:
            if on_off_state:
                print("EVENT: Held 0, Previous song")
                send_uart("B", "2", "0")
                if button_number == 5:
                    print("Button 0 held while off: Resetting the Pi Zero")
                    settings.pi_zero_reset.value = False
                    time.sleep(0.05)
                    settings.pi_zero_reset.value = True
            elif pi_state:
                print("Button 0 held while off: Telling Pi Zero to exit code via serial")
                settings.gauge_pixels.fill((0, 255, 0, 0))
                time.sleep(2)
                settings.gauge_pixels.fill((0, 55, 0, 0))
                send_uart("P", "2")
            elif supervisor.runtime.usb_connected:
                print("Button 0 held while off: Telling Pi Zero to exit code via soft off")
                settings.gauge_pixels.fill((0, 0, 255, 0))
                time.sleep(2)
                settings.gauge_pixels.fill((0, 0, 55, 0))
                settings.pi_zero_soft_off.value = False
                time.sleep(0.1)
                settings.pi_zero_soft_off.value = True
            else:
                print("Button 0 held while off and no USB connection")
                settings.gauge_pixels.fill((255, 0, 0, 0))
                time.sleep(2)
                settings.gauge_pixels.fill((55, 0, 0, 0))
        elif button_number == 1:
            print("EVENT: Held 1, Prev Band")
            send_uart("B", "2", "1")

        elif button_number == 2:
            print("EVENT: Held 2, Randomize Station")
            send_uart("B", "2", "2")

        elif button_number == 3:
            print("EVENT: Held 3, Next Band")
            send_uart("B", "2", "3")

        elif button_number == 4:
            print("EVENT: Held 4, Next Song")
            send_uart("B", "2", "4")

def handle_switches():
    global volume_switch_state, tuning_switch_state
    switch_number, switch_event_type = check_switches()
    if switch_event_type is settings.SWITCH_CCW:
        if switch_number == 0:
            print("EVENT: Switch 0, Off")
            volume_switch_state = False
            standby()
        elif switch_number == 1:
            print("EVENT: Switch 1, Off")
            tuning_switch_state = False

    if switch_event_type == settings.SWITCH_CW:
        if switch_number == 0:
            print("EVENT: Switch 0, On")
            volume_switch_state = True
            resume_from_standby()
        elif switch_number == 1:
            print("EVENT: Switch 1, On")
            tuning_switch_state = True



@atexit.register
def exit_script():
    print("INFO: Exiting")
    #settings.serial.Close()

if settings.REMOTE_ENABLED:
    import ultrasonic_remote

print("STARTUP: Pi Pico Started")
wait_for_pi() # Wait for the Pi Zero to be up and running
wait_for_on_switch()
resume_from_standby()


while True:
    now = time.monotonic()

    # Blink the LED to know the code is running
    if now - led_heartbeat_prev > settings.LED_HEARTBEAT_INTERVAL:
            blink_led()
            #print("DEBUG: Blinking LED at", now)
            led_heartbeat_prev = now

    # Send a heartbeat signal to the Pi Zero
    if now - uart_heartbeat_time > settings.UART_HEARTBEAT_INTERVAL:
            send_uart("H", "Pico")
            #print("DEBUG: Sending heartbeat at", now)
            uart_heartbeat_time = now

    # Go into standby if lost contact with the Pi Zero
    if now - pi_zero_heartbeat_time > settings.PI_ZERO_HEARTBEAT_TIMEOUT:
        print("WARNING: Pi Zero Heartbeat not received")
        pi_zero_heartbeat_time = now
        pi_state = False
        standby()
        wait_for_pi()

    # Ultrasonic remote (This code causes some slow down if enabled)
    if settings.REMOTE_ENABLED and now > settings.REMOTE_SAMPLE_RATE:
        remote_button = ultrasonic_remote.remote_detect()

        if remote_button == 0:
            if on_off_state:
                print("REMOTE: Channel Lower, Prev Station")
                send_uart("B", "1", "1")
            else:
                resume_from_standby()

        elif remote_button == 1:
            volume_dead_zone = settings.DIGITAL_VOLUME_DEAD_ZONE
            volume = max(volume - settings.DIGITAL_VOLUME_INCREMENT, 0)
            if volume == 0 and on_off_state:
                standby()
            send_uart("V", str(volume))
            print("REMOTE: Volume On/Off, Volume down", volume)

        elif remote_button == 2:
            volume_dead_zone = settings.DIGITAL_VOLUME_DEAD_ZONE
            if volume != 0:
                volume = min(volume + settings.DIGITAL_VOLUME_INCREMENT, 1)
            else:
                volume = 0.008
            if not on_off_state:
                resume_from_standby()
            send_uart("V", str(volume))
            print("REMOTE: Sound Mute, Volume Up", volume)

        elif remote_button == 3:
            if on_off_state:
                print("REMOTE: Channel Higher, Next Station")
                send_uart("B", "1", "3")
            else:
                resume_from_standby()

    handle_switches()
    handle_buttons()

    if on_off_state:
        # Switch 0 disables VOLUME_ADC (To allow for standby mode)
        if volume_switch_state:
            # Switch 1 disables volume control, to allow for brightness control.
            if tuning_switch_state:
                check_volume_knob()
            else:
                brightness_control()
            check_tuning_knob()

    uart_message = receive_uart()
    if uart_message:
        #print("UART Received:",uart_message)
        try:
            #Power commands
            if uart_message[0] == "P":
                if len(uart_message) > 1 and uart_message[1]:
                    if on_off_state and uart_message[1] == "0":
                        standby()
                        print("STATE: From Zero: Pi Zero in standby mode")
                    elif uart_message[1] == "1":
                        resume_from_standby()
                        print("STATE: From Zero: Pi Zero resume from standby")
                    elif uart_message[1] == "On":
                        print("STATE: From Zero: Pi Zero is already running")
                        #set_pixels()

            #Motor Angle
            if uart_message[0] == "M":
                #print("Message:",uart_message)
                if len(uart_message) > 1 and uart_message[1]:
                    print("DEBUG: From Zero: New motor angle",uart_message[1])
                    tuning_dead_zone = settings.DIGITAL_TUNING_DEAD_ZONE
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
            print("ERROR: Uart:", error)
