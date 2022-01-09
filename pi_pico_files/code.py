#This code goes onto the Pi Pico
import time
import board
import busio
import digitalio
import analogio
import neopixel
import pwmio
import math
import keypad
import supervisor
import rp2040
from adafruit_simplemath import map_range, constrain


## globals:
# ADC Related:
ADC_0_Prev_Value = None
ADC_1_Prev_Value = None
ADC_0_Prev_Values = []
ADC_1_Prev_Values = []

#Switch related:
switch_0_state = None
switch_1_state = None

#Motor related:
motor_angle = 0
prev_motor_angle = 0

#NeoPIxel related:
neopixel_set_time = None
neopixel_set_timeout = 1.5

def Set_motor(angle, disable = False):  # Set angle in degrees
    global prev_motor_angle, motor_angle

    if disable:
        rp2040.SIN_PWM.duty_cycle = 0
        rp2040.SIN_POS.value = False
        rp2040.SIN_NEG.value = False
        rp2040.COS_PWM.duty_cycle = 0
        rp2040.COS_POS.value = False
        rp2040.COS_NEG.value = False
        return

    motor_angle = angle
    # Do nothing if the angle hasn't changed
#    if angle == prev_motor_angle or angle is None:
 #       return
  #  prev_motor_angle = angle

    # Keep needle within the preset limits
    angle = constrain(angle, rp2040.motor_min_angle, rp2040.motor_max_angle)
    rp2040.uart.write(bytearray(" ".join(["A,1,", str(angle), "\n"]))) # Send angle up to the Pi Zero

    radian = angle * 0.0174  # Convert the angle to a radian (math below only works on radians)
    sin_radian = math.sin(radian)  # Calculate sin
    cos_radian = math.cos(radian)  # Calculate cos

    sin_coil_voltage = round(abs(sin_radian) * rp2040.motor_ref_voltage, 4)  # Calculate voltage needed on coil.
    sin_coil_pwm = round(map_range(sin_coil_voltage, 0, rp2040.motor_ref_voltage, 0, rp2040.pwm_max_value)) # Determine PWM output

    cos_coil_voltage = round(abs(cos_radian) * rp2040.motor_ref_voltage, 4)  # Calculate voltage need on coil.
    cos_coil_pwm = round(map_range(cos_coil_voltage, 0, rp2040.motor_ref_voltage, 0, rp2040.pwm_max_value)) # Determine PWM output

    #print("Angle:",angle, "\tSinV:", sin_coil_voltage, "\tSinPWM:", sin_coil_pwm, "\tCosV", cos_coil_voltage, "\tCosPWM=",cos_coil_pwm)

    # Change the polarity of the coil depending on the sign of the voltage level
    if sin_radian < 0:
        rp2040.SIN_PWM.duty_cycle = sin_coil_pwm
        if rp2040.SIN_DIRECTION:
            SIN_POS.value = True
            SIN_NEG.value = False
        else:
            SIN_POS.value = False
            SIN_NEG.value = True
    else:
        rp2040.SIN_PWM.duty_cycle = sin_coil_pwm
        rp2040.SIN_POS.value = False
        rp2040.SIN_NEG.value = True
    if cos_radian < 0:
        rp2040.COS_PWM.duty_cycle = cos_coil_pwm
        if rp2040.COS_DIRECTION:
            rp2040.COS_POS.value = True
            rp2040.COS_NEG.value = False
        else:
            rp2040.COS_POS.value = False
            rp2040.COS_NEG.value = True
    else:
        rp2040.COS_PWM.duty_cycle = cos_coil_pwm
        if rp2040.COS_DIRECTION:
            rp2040.COS_POS.value = False
            rp2040.COS_NEG.value = True
        else:
            rp2040.COS_POS.value = True
            rp2040.COS_NEG.value = False

def test_motor():
    Set_motor(0)
    time.sleep(1)
    for angle in range(rp2040.motor_min_angle, rp2040.motor_max_angle):
        Set_motor(angle)
        time.sleep(0.05)

def heartbeat():
    rp2040.led.value = not rp2040.led.value if rp2040.on_off_state else False

def check_buttons():
    button_event = rp2040.buttons.events.get()
    switch_event = rp2040.switches.events.get()
    time_ticks = supervisor.ticks_ms()
    for button_num, press_time in enumerate(rp2040.button_press_time):
        if press_time and time_ticks > press_time + rp2040.button_long_press:
            #print("Debug: Button", button_num, "held for", button_long_press, "ms", time_ticks)
            rp2040.button_press_time[button_num] = None
            rp2040.button_held_state[button_num] = True
            return button_num, rp2040.button_held

    if button_event:
        if button_event.pressed:
            #print("Debug: Button",button_event.key_number,"Pressed at",button_event.timestamp)
            rp2040.button_press_time[button_event.key_number] = button_event.timestamp
            return button_event.key_number, rp2040.button_pressed

        if button_event.released:
            rp2040.button_press_time[button_event.key_number] = None
            if rp2040.button_held_state[button_event.key_number] is True:
                #print("Debug: Button",button_event.key_number,"Released after a hold",button_event.timestamp)
                rp2040.button_held_state[button_event.key_number] = False
            else:
                #print("Debug: Button",button_event.key_number,"Released at",button_event.timestamp)
                return button_event.key_number, rp2040.button_released
    if switch_event:
        if switch_event.pressed:
            return switch_event.key_number + rp2040.button_quantity, rp2040.switch_cw
        elif switch_event.released:
            return switch_event.key_number + rp2040.button_quantity, rp2040.switch_ccw
    return None, None

def check_adc():
    global ADC_0_Prev_Values, ADC_1_Prev_Values, ADC_0_Prev_Value, ADC_1_Prev_Value
    global switch_0_state, switch_1_state

    # Switch 0 disables ADC_0 (To allow for standby mode)
    if switch_0_state:
        adc_0_value = round(map_range(rp2040.ADC_0.value,0,rp2040.ADC_Reported_Max, rp2040.ADC_Min, rp2040.ADC_Max))
        ADC_0_Prev_Values.append(adc_0_value)
        if len(ADC_0_Prev_Values) >= rp2040.ADC_Samples:
            adc_0_mean = round(sum(ADC_0_Prev_Values) / float(len(ADC_0_Prev_Values)))
            ADC_0_Prev_Values = []
            if adc_0_mean != ADC_0_Prev_Value:
                ADC_0_Prev_Value = adc_0_mean
                rp2040.uart.write(bytearray(" ".join(["A,0,",str(adc_0_mean),"\n"])))

    # Switch 1 disables ADC_1 (To allow for manual tuning)
    if switch_1_state:
        adc_1_value = round(map_range(rp2040.ADC_1.value,0,rp2040.ADC_Reported_Max, rp2040.ADC_Min, rp2040.ADC_Max))
        ADC_1_Prev_Values.append(adc_1_value)
        if len(ADC_1_Prev_Values) >= rp2040.ADC_Samples:
            adc_1_mean = round(sum(ADC_1_Prev_Values) / float(len(ADC_1_Prev_Values)))
            ADC_1_Prev_Values = []
            if adc_1_mean != ADC_1_Prev_Value:
                ADC_1_Prev_Value = adc_1_mean
                angle = round(map_range(adc_1_mean,rp2040.ADC_Min, rp2040.ADC_Max,rp2040.motor_min_angle, rp2040.motor_max_angle),3)
                Set_motor(angle)

def resume_from_standby():
    if not rp2040.on_off_state:
        print("Info: Resume from standby")
        rp2040.buttons.events.clear()
        rp2040.switches.events.clear()
        rp2040.on_off_state = True
        rp2040.uart.write(bytearray(b"P,1\n"))
        #soft_start()
        #rp2040.pixels.fill((0, 0, 0, rp2040.led_max_brightness))

def standby():
    if rp2040.on_off_state:
        print("Info: Going into standby")
        rp2040.on_off_state = False
        rp2040.uart.write(bytearray(b"P,0\n"))
        soft_stop()

def sweep():
    for angle in range(rp2040.motor_min_angle, rp2040.motor_max_angle):
        Set_motor(angle)
        time.sleep(0.01)

def soft_start():
    for led_brightness in range(rp2040.led_max_brightness):
        angle = map_range(led_brightness, 0, rp2040.led_max_brightness, rp2040.motor_min_angle, rp2040.motor_max_angle)
        rp2040.pixels.fill((0,0,0,led_brightness))
        Set_motor(angle)
        time.sleep(0.01)

def soft_stop():
    global motor_angle
    for led_brightness in range(rp2040.led_max_brightness, 0, -1):
        if motor_angle < rp2040.motor_mid_point:
            angle = map_range(led_brightness, rp2040.led_max_brightness, 0, motor_angle, rp2040.motor_mid_point)
        else:
            angle = map_range(led_brightness, 0, rp2040.led_max_brightness, rp2040.motor_mid_point, motor_angle)
        Set_motor(angle)
        rp2040.pixels.fill((0, 0, 0, led_brightness))
        time.sleep(0.01)
    rp2040.pixels.fill((0, 0, 0, 0))
    Set_motor(rp2040.motor_mid_point,True)

def set_single_pixel(pixel=None):
    global neopixel_set_time
    print("NeoPixel=",pixel)
    if pixel is None:
        rp2040.pixels.fill((0, 0, 0, rp2040.led_max_brightness))
    else:
        rp2040.pixels.fill((0, 0, 0, round(rp2040.led_max_brightness/8)))
        rp2040.pixels[pixel] = (0, 0, 0, 255)
        neopixel_set_time = time.monotonic()

print("RP2040 Started")

def receive_uart():
    line = rp2040.uart.readline() # Read data until "\n" or timeout
    if line:
        try:
            line = line.decode("utf-8") # Convert from bytes to string
            line = line.strip("\n") # Strip end line
            return "".join(line).split(",") # Split into array of commands
        except Exception as e:
            print("UART Error:",e)

soft_start()

while True:
    now = time.monotonic()
    if now - rp2040.led_heartbeat_prev >= rp2040.led_heartbeat_interval:
            heartbeat()
            rp2040.led_heartbeat_prev = now

    if neopixel_set_time:
        if now - neopixel_set_time > neopixel_set_timeout:
            set_single_pixel()
            neopixel_set_time = None

    if rp2040.on_off_state:
        if now - rp2040.uart_heartbeat_prev >= rp2040.uart_heartbeat_interval:
            rp2040.uart.write(bytearray(b"I,RP2040 Heartbeat\n"))
            rp2040.uart_heartbeat_prev = now

        button_number, button_event_type = check_buttons()
        if button_event_type is rp2040.button_released:
            if button_number is 0:
                print("Released 0, Rewind")
                rp2040.uart.write(bytearray(b"B,1,0\n"))
            elif button_number is 1:
                print("Released 1, Previous band")
                rp2040.uart.write(bytearray(b"B,1,1\n"))
            elif button_number is 2:
                print("Released 2, Play/Pause")
                rp2040.uart.write(bytearray(b"B,1,2\n"))
            elif button_number is 3:
                print("Released 3, Next Band")
                rp2040.uart.write(bytearray(b"B,1,3\n"))
            elif button_number is 4:
                print("Released 4, Fast Forward")
                rp2040.uart.write(bytearray(b"B,1,4\n"))

        if button_event_type is rp2040.button_held:
            if button_number is 0:
                print("Held 0, Previous song")
                rp2040.uart.write(bytearray(b"B,2,0\n"))
            elif button_number is 1:
                print("Held 1, Prev Station")
                rp2040.uart.write(bytearray(b"B,2,1\n"))
            elif button_number is 2:
                print("Held 2, Randomize Station")
                rp2040.uart.write(bytearray(b"B,2,2\n"))
            elif button_number is 3:
                print("Held 3, Next Station")
                rp2040.uart.write(bytearray(b"B,2,3\n"))
            elif button_number is 4:
                print("Held 4, Next Song")
                rp2040.uart.write(bytearray(b"B,2,4\n"))

        if button_event_type is rp2040.switch_ccw:
            if button_number is 5:
                #print("Switch 0, Off")
                switch_0_state = False
                standby()
            elif button_number is 6:
                #print("Switch 1, Off")
                switch_1_state = False

        if button_event_type is rp2040.switch_cw:
            if button_number is 5:
                #print("Switch 0, On")
                switch_0_state = True
            elif button_number is 6:
                #print("Switch 1, On")
                switch_1_state = True
        check_adc()
    else:
        switch_event_call = rp2040.switches.events.get() #Watch this switch while in sleep mode
        if switch_event_call:
            if switch_event_call.pressed and switch_event_call.key_number is 0:
                switch_0_state = True
                resume_from_standby()
    uart_message = receive_uart()
    if uart_message:
        try:
            #Power commands
            if uart_message[0] == "P":
                if len(uart_message) > 1 and uart_message[1]:
                    state = uart_message[1]
                    print("UART: on_off_state=",state)
                    if state == "0":
                        standby()
                    elif state == "1":
                        resume_from_standby()

            #Motor Angle
            if uart_message[0] == "M":
                #print("Message:",uart_message)
                if len(uart_message) > 1 and uart_message[1] and rp2040.on_off_state:
                    Set_motor(eval(uart_message[1]))

            #Other Commands
            if uart_message[0] == "C":
                if len(uart_message) > 1 and uart_message[1]:
                    if uart_message[1] == "Sweep":
                        sweep()
                    if uart_message[1] == "light_led":
                        set_single_pixel(eval(uart_message[2]))



        except Exception as error:
            print("Uart Error:",error)
