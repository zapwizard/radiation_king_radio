#!/usr/bin/python3
import atexit
import configparser
import glob
import os
import random
import sys
import time
from collections import deque

import mutagen
import pygame
import settings
from statistics import mean
import math

# os.environ["SDL_AUDIODRIVER"] = "dsp"

print("Starting up")
clock = pygame.time.Clock()

neopixel = False
volume = float(0.05)
volume_time = time.time()
station_num = int(0)
station_list = []
stations = []
total_station_num = int(0)
radio_band = int(0)
radio_band_list = []
radio_band_total = int(0)
running = True
neopixels = None
active_station = None
gpio_actions = {}
led_state = True
on_off_state = True
master_start_time = time.time()

tuning_volume = 0
tuning_sensitivity = 5
tuning_locked = False
tuning_prev_angle = None

if settings.PI:

    if not os.geteuid() == 0:
        sys.exit('This script must be run as root!')

    try:
        import neopixel_spi

        neopixel_order = neopixel_spi.GRBW  # For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
        neopixels = neopixel_spi.NeoPixel_SPI(settings.neopixel_pin, settings.neopixel_number,
                                              brightness=settings.neopixel_brightness, auto_write=True,
                                              pixel_order=neopixel_order, bit0=0b10000000)  # Raspberry Pi wiring!
        neopixel = True
        print("NeoPixels initialized")
        neopixels.fill((0, 0, 0, round(settings.neo_pixel_default / 10)))
    except Exception as e:
        neopixel = False
        print ("No NeoPixels found", e)

    try:
        import qwiic_scmd

        myMotor = qwiic_scmd.QwiicScmd()

        if not myMotor.connected:
            print("Motor Driver not connected. Check connections.", file=sys.stderr)
        else:
            myMotor.begin()
            motor = True
        time.sleep(0.250)

        motor_angle = 0
        prev_motor_angle = 0

        # Zero Motor Speeds
        myMotor.set_drive(settings.motor_sin, 0, 0)
        myMotor.set_drive(settings.motor_cos, 0, 0)
        myMotor.enable()
        print("Motor Driver initialized.")
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("Motor driver failed: (%s)" % err, e)

    try:
        import board
        import adafruit_pcf8591.pcf8591 as PCF
        from adafruit_pcf8591.analog_in import AnalogIn
        from adafruit_pcf8591.analog_out import AnalogOut

        i2c = board.I2C()
        pcf = PCF.PCF8591(i2c)

        ADC_0 = AnalogIn(pcf, PCF.A0)
        ADC_1 = AnalogIn(pcf, PCF.A1)
        ADC_0_Enabled = False
        # DAC = AnalogOut(pcf, PCF.OUT)
        ADC_0_Prev_Angle = 0
        ADC_0_Prev_Values = []
        ADC_0_Prev_Raw_Value = 0

        ADC_1_Prev_Value = 0
        ADC_1_Prev_Values = []
        ADC_1_Prev_Raw_Value = 0

        ADC = True
        # DAC = True
    except:
        ADC = False
        # DAC = False

    try:
        import buttonshim

        buttonshim.set_pixel(0x16, 0x00, 0x00)
    except:
        buttonshim = None
        print("No button shim detected")

    button_held = False
    if buttonshim:
        @buttonshim.on_release(buttonshim.BUTTON_A)
        def button_a(button, pressed):
            global button_held
            if button_held:
                button_held = False
            elif on_off_state:
                if active_station:
                    active_station.rewind()


        @buttonshim.on_hold(buttonshim.BUTTON_A, hold_time=settings.hold_time)
        def button_a(button):
            global button_held
            if on_off_state:
                if active_station:
                    active_station.prev_song()
            button_held = True


        @buttonshim.on_release(buttonshim.BUTTON_B)
        def button_b(button, pressed):

            global button_held, volume
            if button_held:
                button_held = False
            elif on_off_state:
                prev_band()
                # volume = set_volume_level(volume, "down")


        @buttonshim.on_hold(buttonshim.BUTTON_B, hold_time=settings.hold_time)
        def button_b(button):
            global button_held, volume
            if on_off_state:
                prev_station()
                # volume = set_volume_level(volume, "down")
                # prev_band()
            button_held = True


        @buttonshim.on_release(buttonshim.BUTTON_C)
        def button_c(button, pressed):  # sourcery skip: merge-else-if-into-elif
            global button_held
            if button_held:
                button_held = False
            else:
                if active_station:
                    active_station.play_pause()


        @buttonshim.on_hold(buttonshim.BUTTON_C, hold_time=settings.hold_time)
        def button_c(button):
            global button_held
            if on_off_state and active_station:
                active_station.randomize_station()
                active_station.next_song()
            button_held = True


        @buttonshim.on_release(buttonshim.BUTTON_D)
        def button_d(button, pressed):
            global button_held, volume
            if button_held:
                button_held = False
            elif on_off_state:
                next_band()
                # volume = set_volume_level(volume, "up")


        @buttonshim.on_hold(buttonshim.BUTTON_D, hold_time=settings.hold_time)
        def button_d(button):
            global button_held, volume
            if on_off_state:
                next_station()
                # next_band()
                # volume = set_volume_level(volume, "up")
            button_held = True


        @buttonshim.on_release(buttonshim.BUTTON_E)
        def button_e(button, pressed):
            global button_held
            if button_held:
                button_held = False
            elif on_off_state:
                if active_station:
                    active_station.fast_forward()


        @buttonshim.on_hold(buttonshim.BUTTON_E, hold_time=settings.hold_time)
        def button_e(button):
            global button_held
            if on_off_state:
                if active_station:
                    active_station.next_song()
                # next_station()
            button_held = True

    try:
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)  # Using GPIO numbering
        gpio_available = True
        for pin in settings.GPIO_ACTIONS.keys():
            print("Initialing pin %s as action '%s'" % (pin, settings.GPIO_ACTIONS[pin]))
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            gpio_actions[pin] = settings.GPIO_ACTIONS[pin]
        GPIO.setup(17, GPIO.IN)  # On off shim
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("GPIO UNAVAILABLE (%s)" % err, e)
        gpio_available = False

    # Import i2c rotary encoder stuff
    try:
        from adafruit_seesaw import seesaw, neopixel, rotaryio, digitalio

        try:
            import _pixelbuf
        except ImportError:
            import adafruit_pypixelbuf as _pixelbuf

        i2c_rotary_encoder = seesaw.Seesaw(board.I2C(), 0x36)

        rotary = rotaryio.IncrementalEncoder(i2c_rotary_encoder)

        i2c_rotary_encoder.pin_mode(24, i2c_rotary_encoder.INPUT_PULLUP)
        rotary_switch = digitalio.DigitalIO(i2c_rotary_encoder, 24)
        rotary_switch_prev = True

        rotary_pixel = neopixel.NeoPixel(i2c_rotary_encoder, 6, 1)
        rotary_pixel.brightness = 0.1

        rotary_value = 0
        rotary_prev_value = 0
        rotary_speed = 0.2
        rotary_pixel_color = None

    except Exception as e:
        _, err, _ = sys.exc_info()
        print("Rotary Encoder failed (%s)" % err, e)
        rotary = None

else:
    print("Not running on a Raspberry Pi")

try:
    print("Starting sound initialization")

    pygame.mixer.quit()
    pygame.mixer.init(44100, -16, 2, 4096)
    if pygame.mixer.get_init():
        print("Sound initialized")
    else:
        print("Sound failed to initialize")
except Exception as e:
    sys.exit("No sound supported" + str(e))

print("Starting pygame initialization")
os.environ["SDL_VIDEODRIVER"] = "dummy"  # Make a fake screen
os.environ['SDL_AUDIODRIVER'] = 'alsa'
pygame.display.set_mode((1, 1))
pygame.init()


# Reserve a sound channel for static sounds
print("Loading static sounds (Ignore the underrun errors)")
pygame.mixer.set_reserved(1)
pygame.mixer.Channel(1)

static_sounds = {}
i = 0
for file in sorted(os.listdir(settings.static_sound_folder)):
    if file.endswith(".ogg"):
        static_sounds[i] = pygame.mixer.Sound("./" + settings.static_sound_folder + "/" + file)
        i += 1
print("Loaded", len(static_sounds), "static sound chunks")


def Set_motor(angle):  # Set angle in degrees
    global prev_motor_angle, motor_angle

    angle = round(angle, 3)
    if motor_angle != angle:
        motor_angle = angle

    # Do nothing if the angle hasn't changed
    if angle == prev_motor_angle or angle is None:
        return
    prev_motor_angle = angle

    # Keep needle within the preset limits
    angle = min(angle, settings.motor_max_angle)
    angle = max(angle, settings.motor_min_angle)
    radian = angle * 0.0174  # Convert the angle to a radian (math below only works on radians)
    sin_radian = math.sin(radian)  # Calculate sin
    cos_radian = math.cos(radian)  # Calculate cos

    sin_coil_voltage = abs(sin_radian) * settings.motor_vcc  # Calculate voltage needed on coil.
    sin_coil_pwm = expand(sin_coil_voltage, 0, settings.motor_vcc, 0, settings.max_pwm_resolution)

    cos_coil_voltage = abs(cos_radian) * settings.motor_vcc  # Calculate voltage need on coil.
    cos_coil_pwm = expand(cos_coil_voltage, 0, settings.motor_vcc, 0, settings.max_pwm_resolution)

    # print(angle, "Deg / sinRadian =", round(sin_radian, 3), sin_coil_pwm, "cosRadian=", round(cos_radian, 3),
    #       cos_coil_pwm)

    # Change the polarity of the coil depending on the sign of the voltage level
    if sin_radian <= 0:
        myMotor.set_drive(settings.motor_sin, settings.backward, sin_coil_pwm)
    else:
        myMotor.set_drive(settings.motor_sin, settings.forward, sin_coil_pwm)

    if cos_radian <= 0:
        myMotor.set_drive(settings.motor_cos, settings.backward, cos_coil_pwm)
    else:
        myMotor.set_drive(settings.motor_cos, settings.forward, cos_coil_pwm)

def load_saved_settings():
    print("Loading saved settings")
    saved_ini = configparser.ConfigParser()
    # Load saved settings:
    try:
        assert os.path.exists(settings.save_file)
        saved_ini.read(settings.save_file, encoding=None)
    except Exception as error:
        print("Error reading the following:", str(error))

    try:
        saved_volume = float(saved_ini.get('audio', 'volume'))
        print("Loaded saved volume:", saved_volume)
    except Exception as error:
        saved_volume = 0.05
        print("Could not read volume setting in", str(error))

    try:
        saved_station_num = int(saved_ini.get('audio', 'station'))
        print("Loaded saved station:", saved_station_num)
    except Exception as error:
        saved_station_num = 0
        print("Could not read station setting in", str(error))

    try:
        saved_band_num = int(saved_ini.get('audio', 'band'))
        print("Loaded saved band:", saved_band_num)
    except Exception as error:
        saved_band_num = 0
        print("Could not read radio band setting in", str(error))
    return saved_volume, saved_station_num, saved_band_num


def expand(old_value, old_min, old_max, new_min, new_max):
    old_range = old_max - old_min
    new_range = new_max - new_min
    return ((old_value - old_min) * new_range / old_range) + new_min


def blink_led():
    global led_state
    if led_state:
        buttonshim.set_pixel(0x00, 0x32, 0x00)
        led_state = False
    else:
        buttonshim.set_pixel(0x00, 0x00, 0x00)
        led_state = True


def check_adc():
    global volume, motor_angle
    global ADC_0, ADC_0_Prev_Angle, ADC_0_Prev_Raw_Value, ADC_0_Prev_Values
    global ADC_1, ADC_1_Prev_Value, ADC_1_Prev_Raw_Value, ADC_1_Prev_Values
    global ADC_0_Enabled

    # ADC_0 is used for tuning
    ADC_0_Enabled = True  # Debug
    if ADC_0_Enabled:
        ADC_0_Prev_Values.append(round(ADC_0.value / 255))
        if len(ADC_0_Prev_Values) == settings.ADC_Samples:
            ADC_0_Value = round(mean(ADC_0_Prev_Values))
            ADC_0_Prev_Raw_Value = ADC_0_Value

            # Self calibrate min and max settings
            if ADC_0_Value < settings.ADC_0_Min:
                settings.ADC_0_Min = ADC_0_Value
                print("New ADC_0_Min =", settings.ADC_0_Min)
            if ADC_0_Value > settings.ADC_0_Max:
                settings.ADC_0_Max = ADC_0_Value
                print("New ADC_0_Max =", settings.ADC_0_Max)

            angle = round(expand(ADC_0_Value, settings.ADC_0_Min, settings.ADC_0_Max, settings.motor_min_angle,
                           settings.motor_max_angle), 1)
            if angle != ADC_0_Prev_Angle:
                ADC_0_Prev_Angle = angle
                motor_angle = angle
                # print("ADC_0 Mean = ", ADC_0_Value, ADC_0_Prev_Values, angle)
                # print("Tune position =", value, "/", settings.motor_min_angle, settings.motor_max_angle)
            ADC_0_Prev_Values = []

    # ADC_1 disables ADC_0 (For digital tuning without the knob changing the station)
    # (The ADC was just used as a convenient i2c connected GPIO)
    ADC_1_Prev_Values.append(ADC_1.value / 255)
    if len(ADC_1_Prev_Values) == settings.ADC_Samples:
        ADC_1_Value = round(mean(ADC_1_Prev_Values), 1)
        ADC_1_Prev_Raw_Value = ADC_1_Value
        ADC_1_Value -= ADC_1_Value % -1000
        #
        # # Self calibrate min and max settings
        if ADC_1_Value < settings.ADC_1_Min:
            settings.ADC_1_Min = ADC_1_Value
            print("New ADC_1_Min =", settings.ADC_1_Min)
        if ADC_1_Value > settings.ADC_1_Max:
            settings.ADC_1_Max = ADC_1_Value
            print("New ADC_1_Max =", settings.ADC_1_Max)

        ADC_1_Value = int(round(expand(ADC_1_Value, settings.ADC_1_Min, settings.ADC_1_Max, 0, 1)))

        if ADC_1_Value != ADC_1_Prev_Value:
            ADC_1_Prev_Value = ADC_1_Value
            # print("ADC_1_Value=", value)
            if ADC_1_Value > 32000:  # Use ADC_1 input to disable ADC_0
                ADC_0_Enabled = True
            else:
                ADC_0_Enabled = False


def clamp(number, minimum, maximum):
    return max(min(maximum, number), minimum)


def set_volume_level(volume_level, direction=None):
    global volume, volume_time

    # Volume level acceleration
    if time.time() - volume_time < settings.rotary_speed:
        step = 0.02
    else:
        step = settings.volume_step

    if direction == "up":
        volume_level += step
    elif direction == "down":
        volume_level -= step

    volume = clamp(round(float(volume_level), 3), settings.volume_min, 1)
    pygame.mixer.music.set_volume(volume)
    if volume > 0:
        static_volume = max(round(volume / settings.static_volume,3), settings.static_volume_min)
    else:
        static_volume = 0
    pygame.mixer.Channel(1).set_volume(static_volume)
    print("Volume =", volume, "Static_volume = ", static_volume)

    volume_time = time.time()
    return volume


def on_off():
    global on_off_state, motor_angle
    if on_off_state:
        on_off_state = False
        if active_station:
            active_station.stop()
        pygame.mixer.Channel(1).stop()
        snd_off = pygame.mixer.Sound("sounds/UI_Pipboy_Radio_Off.ogg")
        snd_off.set_volume(settings.effects_volume)
        snd_off.play()
        myMotor.disable()
        if neopixels:
            neopixels.fill((0, 0, 0, 0))
        if rotary:
            set_rotary_pixel(32, 0.1)
        save_settings()
        print("Going into standby")
    else:
        on_off_state = True
        snd_on = pygame.mixer.Sound("sounds/UI_Pipboy_Radio_On.ogg")
        snd_on.set_volume(settings.effects_volume)
        snd_on.play()
        myMotor.enable()
        previous_motor_angle = motor_angle
        for angle in range(settings.motor_min_angle, settings.motor_max_angle):
            play_static()
            Set_motor(angle)
            if neopixels:
                neopixels.fill((0, 0, 0, round(expand(angle,settings.motor_min_angle,settings.motor_max_angle,0,settings.neo_pixel_default))))
            time.sleep(0.005)
        time.sleep(0.5)
        play_static(False)
        Set_motor(previous_motor_angle)
        tuning()
        if active_station:
            active_station.play_song()
        if rotary:
            set_rotary_pixel(None)
        print("Resume from standby")


def handle_action(action):
    print("Action = ", action)
    if action == settings.GPIO_ACTIONS["power_off"]:
        save_settings()
        sys.exit()


def check_gpio_input():
    global gpio_actions
    for gpio in gpio_actions.keys():
        if not GPIO.input(gpio):
            handle_action(gpio_actions[gpio])


def handle_event(event):
    global running, active_station
    if event.type == pygame.QUIT:
        print("Quit called")
        running = False
    elif event.type == settings.EVENTS['SONG_END']:
        if active_station and active_station.state == active_station.STATES['playing']:
            active_station.files.rotate(-1)
            active_station.song_lengths.rotate(-1)
            active_station.play_song(False)
            # print("Song ended, Playing next song")
    elif event.type == settings.EVENTS['PLAYPAUSE']:
        print("Play / Pause")
        active_station.pause_play()
    elif event.type == settings.EVENTS['BLINK']:
        blink_led()
    else:
        print("Event:", event)


def check_rotary():
    global rotary, rotary_value, rotary_prev_value, volume
    rotary_value = -rotary.position

    # Volume control
    if rotary_prev_value < rotary_value < 65000:
        volume = set_volume_level(volume, "up")
        rotary_prev_value = rotary_value
    elif rotary_value < rotary_prev_value and rotary_value < 65000:
        volume = set_volume_level(volume, "down")
        rotary_prev_value = rotary_value
    # print("rotary_value=", rotary_value)


def check_rotary_button():
    global rotary, rotary_switch, rotary_switch_prev
    value = rotary_switch.value
    if value != rotary_switch_prev:
        if value:
            on_off()
            # print("Rotary button released")
            # set_rotary_pixel(None)
        # else:
        #     print("Rotary button pressed")
        #     set_rotary_pixel(32, 0.1)
        rotary_switch_prev = rotary_switch.value


def set_rotary_pixel(color=None, brightness=0.05):
    global rotary_pixel, rotary_pixel_color
    if color:
        rotary_pixel.fill(_pixelbuf.colorwheel(color))
    else:
        rotary_pixel.fill(0)
    if brightness:
        rotary_pixel.brightness = brightness


def get_radio_bands(station_folder):
    print("Starting folder search in :", station_folder)

    radio_bands = []
    for folder in sorted(os.listdir(station_folder)):
        if os.path.isdir(station_folder + folder):
            # print("Starting radio band search in :", station_folder + folder)
            sub_radio_bands = []
            for sub_folder in sorted(os.listdir(station_folder + folder)):  # Search root audio folders for sub-folders
                path = os.path.join(station_folder, folder, sub_folder)
                if os.path.isdir(path):
                    # print("Starting song search in folder:", path)
                    if len(glob.glob(path + "/*.ogg")) == 0:
                        print("WARNING: No .ogg files in:", sub_folder)
                        continue

                    station_data = None
                    station_ini_parser = configparser.ConfigParser()
                    station_meta_data_file = os.path.join(path, "station.ini")

                    try:
                        assert os.path.exists(station_meta_data_file)
                        station_ini_parser.read(station_meta_data_file)
                    except Exception as error:
                        print("Error reading:", station_meta_data_file, str(error))

                    try:
                        if station_ini_parser.has_section("metadata"):
                            station_name = station_ini_parser.get('metadata', 'station_name')
                            station_ordered = eval(station_ini_parser.get('metadata', 'ordered'))
                            # print("Loading station:", station_name, "Ordered =", station_ordered)
                        else:
                            print("Could not find a [metadata] section in:", station_meta_data_file)
                            station_name = folder
                            station_ordered = True
                    except Exception as error:
                        print("Error reading:", station_meta_data_file, str(error))

                    if not settings.reset_cache:
                        try:
                            station_data = eval(station_ini_parser.get('cache', 'station_data'))
                            print("Loaded cached station data from", station_meta_data_file)
                        except Exception as error:
                            print(str(error), "Could not read cache file in", station_meta_data_file)
                        try:
                            if not eval(str(station_data[3])):  # Randomized cached stations
                                seed = random.random()
                                random.Random(seed).shuffle(station_data[2])  # station_files
                                random.Random(seed).shuffle(station_data[4])  # station_lengths
                                # print("randomizing", folder)
                        except Exception as error:
                            print(str(error), "station_data[3]=",station_data[3])
                    else:
                        station_files = []
                        station_lengths = []

                        for song_file in sorted(os.listdir(path)):
                            if song_file.endswith(".ogg"):
                                station_files.append(os.path.join(path, song_file))
                                try:
                                    station_lengths.append(mutagen.File(os.path.join(path, song_file)).info.length)
                                except Exception as error:
                                    print("Mutagen error:", str(error), "in file", song_file)
                        total_length = sum(station_lengths)

                        if not station_ordered:
                            seed = random.random()
                            random.Random(seed).shuffle(station_files)
                            random.Random(seed).shuffle(station_lengths)
                            # print("randomizing", folder)

                        if not station_data:
                            station_data = station_name, folder, station_files, station_ordered, station_lengths, total_length

                            try:
                                station_ini_parser.read(station_meta_data_file, encoding=None)
                                if not station_ini_parser.has_section("cache"):
                                    station_ini_parser.add_section("cache")
                                    print("Adding the Cache section to", station_meta_data_file)
                                # else:
                                # print("There is already a cache section in", station_meta_data_file)
                            except Exception as error:
                                print(str(error), "in", station_meta_data_file)

                            try:
                                station_ini_file = open(station_meta_data_file, 'w')
                            except Exception as error:
                                print("Failed to open cache file", station_meta_data_file, "|", str(error))

                            try:
                                station_ini_parser.set("cache", "station_data", str(station_data))
                                station_ini_parser.write(station_ini_file)
                                print("Saved Cache to %s, station %s" % (station_meta_data_file, station_name))
                                station_ini_file.close()
                            except Exception as error:
                                print("Failed to save cache to", station_meta_data_file, "/", str(error))
                    if len(station_data) > 0:
                        sub_radio_bands.append(station_data)
        if len(sub_radio_bands) > 0:
            radio_bands.append(sub_radio_bands)
    return radio_bands


def get_station_pos(station_number):
    global total_station_num, tuning_sensitivity
    return round(
        expand(
            station_number,
            0,
            total_station_num - 1,
            settings.motor_min_angle + (tuning_sensitivity / settings.tuning_near),
            settings.motor_max_angle - (tuning_sensitivity / settings.tuning_near),
        ),
        2,
    )


def get_nearest_station(angle):
    global tuning_sensitivity, total_station_num
    nearest_station = round(
        expand(
            angle,
            settings.motor_min_angle + (tuning_sensitivity / settings.tuning_near),
            settings.motor_max_angle - (tuning_sensitivity / settings.tuning_near),
            0,
            total_station_num - 1,
        )
    )
    if nearest_station >= total_station_num:
        nearest_station = total_station_num - 1
    return nearest_station

def play_static(play = True):
    global static_sounds, volume
    if pygame.mixer.Channel(1).get_busy():
        if not play:
            pygame.mixer.Channel(1).stop()
    elif play:
        random_snd = random.randrange(0, len(static_sounds) - 1)
        pygame.mixer.Channel(1).play(static_sounds[random_snd])
        if volume > 0:
            pygame.mixer.Channel(1).set_volume(max(round(volume / settings.static_volume,3), settings.static_volume_min))
        else:
            pygame.mixer.Channel(1).set_volume(0)

def tuning():
    global motor_angle, volume, static_sounds, tuning_locked, tuning_prev_angle
    global active_station, tuning_volume, tuning_sensitivity

    nearest_station_num = get_nearest_station(motor_angle)
    station_position = get_station_pos(nearest_station_num)
    range_to_station = abs(station_position - motor_angle)
    lock_on_tolerance = round(tuning_sensitivity / settings.tuning_lock_on, 3)

    # Play at volume with no static when needle is close to station position
    if range_to_station <= lock_on_tolerance:
        tuning_volume = volume
        if not tuning_locked:
            if active_station:
                print("Locked to station #", nearest_station_num, "at angle:", station_position, "Needle=",
                      motor_angle, "lock on tolerance=", lock_on_tolerance)
                pygame.mixer.music.set_volume(volume)
            play_static(False)
            tuning_locked = True
            if neopixels:
                neopixels.fill((0, 0, 0, settings.neo_pixel_default))

    # Start playing audio with static when the needle get near a station position
    elif lock_on_tolerance < range_to_station < tuning_sensitivity / settings.tuning_near:
        tuning_volume = round(volume / range_to_station, 3)
        pygame.mixer.music.set_volume(tuning_volume)
        if neopixels:
            neopixels.fill((0, 0, 0, settings.neo_pixel_default - 2))

        if active_station and active_station is not None:
            play_static(True)
            tuning_locked = False
            # print("Lost lock on station #", nearest_station_num, "at angle:", station_position, "Needle=",
            #       motor_angle, "lock on tolerance=", lock_on_tolerance)
        else:
            print("Nearing station #", nearest_station_num, "at angle:", station_position, "Needle=",
                  motor_angle, "near tolerance =", lock_on_tolerance)
            select_station(nearest_station_num, False)

    # Stop any music and play just static if the needle is not near any station position
    else:
        if neopixels:
            neopixels.fill((0, 0, 0, settings.neo_pixel_default - 6))
        if active_station and active_station is not None:
            print("No active station. Nearest station # is:", nearest_station_num, "at angle:", station_position,
                  "Needle=", motor_angle, "tuning_sensitivity =", tuning_sensitivity)
            active_station.stop()
            pygame.mixer.music.stop()
            active_station = None
            tuning_locked = False
        play_static(True)


def select_station(new_station_num, manual=False):
    global station_num, active_station, total_station_num, motor_angle, tuning_locked, stations
    if new_station_num > total_station_num or new_station_num < 0:
        print("Selected an invalid station number:", new_station_num, "/", total_station_num)
    else:
        if motor and manual:
            motor_angle = get_station_pos(new_station_num)
            tuning_locked = False
            Set_motor(motor_angle)

        if active_station and station_num != new_station_num:
            active_station.stop()
        active_station = stations[new_station_num]

        print("Changing to station number", new_station_num, "at angle =", motor_angle)
        station_num = new_station_num
        active_station.play_song()


def prev_station():
    global station_num, total_station_num
    station_num = station_num - 1
    if station_num < 0:
        station_num = 0
        print("At the beginning of the station list", station_num, "/", total_station_num)
    else:
        print("Previous station", station_num, "/", total_station_num)
    select_station(station_num, True)


def next_station():
    global station_num, total_station_num
    station_num = station_num + 1
    if station_num > total_station_num - 1:
        station_num = total_station_num - 1
        print("At end of the station list", station_num, "/", total_station_num)
    else:
        print("Next station", station_num, "/", total_station_num)
    select_station(station_num, True)


def select_band(new_band_num):
    global radio_band_list, radio_band, total_station_num, tuning_sensitivity, radio_band_total, station_list
    global stations, motor_angle, tuning_locked, active_station, volume
    if active_station:
        active_station.stop()

    if new_band_num > radio_band_total or new_band_num < 0:
        print("Selected an invalid band number:", new_band_num, "/", radio_band_total)
    else:
        print("Changing to band number", new_band_num)
        motor_angle_prev = motor_angle
        Set_motor(settings.motor_min_angle)
        radio_band = new_band_num
        snd_band = pygame.mixer.Sound("sounds/Band_Change.ogg")
        snd_band.set_volume(volume / settings.band_change_volume)
        snd_band.play()

        for angle in range(settings.motor_min_angle,
                           round(expand(new_band_num, 0, len(radio_band_list) - 1,
                                        settings.motor_min_angle, settings.motor_max_angle))):
            Set_motor(angle)
            time.sleep(0.004)
        time.sleep(0.4)
        Set_motor(motor_angle_prev)

    station_list = radio_band_list[new_band_num]

    total_station_num = len(station_list)
    tuning_sensitivity = settings.motor_steps / total_station_num
    print("Tuning angle separation =", tuning_sensitivity, "Number of stations:", total_station_num)

    stations = []
    for radio_station in station_list:
        station_folder = radio_station[1] + "/"
        station_name = radio_station[0]
        stations.append(RadioClass(station_name, station_folder, radio_station))

    # active_station = stations[get_nearest_station(motor_angle)]
    # active_station.play_song(True)
    tuning()


def prev_band():
    global radio_band, radio_band_total
    radio_band = radio_band - 1
    if radio_band < 0:
        radio_band = 0
        print("At the beginning of the band list", radio_band, "/", radio_band_total)
    else:
        print("Previous radio band", radio_band, "/", radio_band_total)
    select_band(radio_band)


def next_band():
    global radio_band, radio_band_total
    radio_band = radio_band + 1
    if radio_band > radio_band_total:
        radio_band = radio_band_total
        print("At end of the band list", radio_band, "/", radio_band_total)
    else:
        print("Next radio band", radio_band, "/", radio_band_total)
    select_band(radio_band)


def run():
    global running, neopixel, station_num, total_station_num, clock, neopixels, stations, buttonshim, ADC
    global rotary, motor_angle, volume, motor, tuning_sensitivity, radio_band, radio_band_total, radio_band_list
    running = True

    radio_band_list = get_radio_bands(settings.stations_root_folder)
    radio_band_total = len(radio_band_list) - 1

    snd_on = pygame.mixer.Sound("sounds/UI_Pipboy_Radio_On.ogg")
    snd_on.set_volume(settings.effects_volume)
    snd_on.play()

    play_static()

    if settings.PI:
        for angle in range(settings.motor_min_angle, settings.motor_max_angle):
            Set_motor(angle)
            if neopixels:
                neopixels.fill((0, 0, 0, round(
                    expand(angle, settings.motor_min_angle, settings.motor_max_angle, 0, settings.neo_pixel_default))))
            time.sleep(0.005)
        if buttonshim:
            pygame.time.set_timer(settings.EVENTS['BLINK'], 1000)

    volume, station_num, radio_band = load_saved_settings()

    select_band(radio_band)

    print("******Fallout Radiation King is running with", total_station_num, "radio stations*****")

    while running:
        for event in pygame.event.get():
            handle_event(event)
        if on_off_state:
            if settings.PI:
                if gpio_available:
                    check_gpio_input()
                if ADC:
                    check_adc()
                    if motor:
                        Set_motor(motor_angle)
                    tuning()
                if rotary:
                    check_rotary()
                    check_rotary_button()
        else:
            check_rotary_button()
        clock.tick(200)

    try:
        pygame.mixer.quit()
        pygame.time.set_timer(settings.EVENTS['BLINK'], 0)
        if neopixel:
            neopixels.fill((0, 0, 0, 0))
        if buttonshim:
            buttonshim.set_pixel(0x00, 0x00, 0x00)

    except Exception as error:
        print(error)


class Radiostation:
    global volume, tuning_volume, master_start_time
    STATES = {
        'stopped': 0,
        'playing': 1,
        'paused': 2
    }

    def __init__(self, *args, **kwargs):

        self.label = None
        self.directory = None
        self.files = deque()
        self.song_lengths = deque()
        self.total_length = []
        self.song_length = 0
        self.state = self.STATES['stopped']
        self.station_length = 0
        self.filename = 0
        self.new_selection = True
        self.last_filename = None
        self.start_time = master_start_time
        self.sum_of_song_lengths = 0
        self.start_pos = 0
        self.last_play_position = 0
        self.last_playtime = 0
        pygame.mixer.music.set_endevent(settings.EVENTS['SONG_END'])

    def play_song(self, new_selection=True):
        global volume
        self.start_pos = 0
        if self.files:
            if self.files[0].endswith("Silence.ogg"):
                print("Radio off")
                self.stop()
            else:
                if new_selection:  # If changed stations manually
                    self.start_pos = max(time.time() - self.start_time, 0)
                    # print("Time based start_pos =", round(self.start_pos, 3))

                    #  Subtract time until we are below the station length
                    if self.station_length and self.start_pos > self.station_length:
                        print("start_pos longer than station length", round(self.start_pos, 3), self.station_length)
                        while self.start_pos > self.station_length:
                            print("Looping station")
                            self.start_pos = self.start_pos - self.station_length

                    #  Find where in the station list we should be base on start position
                    self.song_length = self.song_lengths[0]  # length of the current song
                    if self.song_length and self.start_pos > self.song_length:
                        print("Start_pos longer than song length", round(self.start_pos, 3), self.song_length)

                        while self.start_pos > self.song_length:
                            # print("Skipping song", self.song_length)
                            self.files.rotate(-1)
                            self.song_lengths.rotate(-1)
                            self.start_pos = self.start_pos - self.song_length
                            self.song_length = self.song_lengths[0]
                        #
                        # self.sum_of_song_lengths = sum(lengths[0:i])
                        # self.start_pos = self.start_pos - self.sum_of_song_lengths
                        self.start_time = time.time() - self.start_pos
                        # print("Jumping to song index: :", i,
                        #       "New Song Length =", lengths[i],
                        #       "start_pos =", round(self.start_pos, 3),
                        #       "self.sum_of_song_lengths", self.sum_of_song_lengths
                        #       )
                    self.new_selection = False
                else:
                    # print("Same station, new song")
                    self.start_pos = 0
                    self.start_time = time.time()

                self.filename = self.files[0]
                song = self.filename

                print("Playing =", self.filename,
                      "length =", str(round(self.song_lengths[0], 2)),
                      "start_pos =", str(round(self.start_pos, 2))
                      )

                pygame.mixer.music.load(song)
                pygame.mixer.music.set_volume(tuning_volume)
                try:
                    pygame.mixer.music.play(0, self.start_pos)
                except:
                    pygame.mixer.music.play(0, 0)

                self.state = self.STATES['playing']

    def play(self):
        if self.state == self.STATES['paused']:
            pygame.mixer.music.unpause()
            self.state = self.STATES['playing']
        else:
            self.play_song(False)
        print("Music resumed")

    def play_pause(self):
        print("Play/pause triggered")
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.state = self.STATES['playing']
            print("Music Paused")
        else:
            pygame.mixer.music.unpause()
            self.state = self.STATES['playing']
            print("Music Resumed")

    def pause(self):
        self.state = self.STATES['paused']
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.state = self.STATES['paused']
        print("Music paused")

    def stop(self):
        self.state = self.STATES['stopped']
        if self.filename:
            self.last_filename = self.filename
            self.last_play_position = pygame.mixer.music.get_pos()
            self.last_playtime = time.time()
        settings.ACTIVE_SONG = None
        pygame.mixer.music.stop()
        # print("Music stopped")

    def next_song(self):
        self.files.rotate(-1)
        self.song_lengths.rotate(-1)
        self.start_time = time.time()
        self.play_song(False)
        print("Next song")

    def prev_song(self):
        self.files.rotate(1)
        self.song_lengths.rotate(1)
        self.start_time = time.time()
        self.play_song(False)
        print("Prev song")

    def randomize_station(self):
        seed = random.random()
        random.Random(seed).shuffle(self.files)
        random.Random(seed).shuffle(self.song_lengths)
        print("Randomized song order")


    def fast_forward(self):
        self.start_time = self.start_time - settings.fast_forward_increment
        if self.start_time < master_start_time:
            master_start_time = self.start_time
        print("Fast forward", settings.fast_forward_increment, self.start_time, master_start_time)
        self.play_song()


    def rewind(self):
        self.start_time = max(self.start_time + settings.rewind_increment, master_start_time)
        print("Rewind", settings.fast_forward_increment, self.start_time, master_start_time)
        self.play_song()

class RadioClass(Radiostation):
    def __init__(self, station_name, station_folder, station_data, *args, **kwargs):
        # self.station_data = [folder, station_name, station_files, station_ordered, station_lengths]
        super(RadioClass, self).__init__(self, *args, **kwargs)
        self.label = station_name
        self.directory = station_folder
        self.files = deque(station_data[2])
        self.song_lengths = deque(station_data[4])
        self.total_length = station_data[5]

def save_settings():
    global volume, station, radio_band
    saved_ini = configparser.ConfigParser()
    try:
        assert os.path.exists(settings.save_file)
        saved_ini.read(settings.save_file)
    except Exception as e:
        print("Error reading the following:", str(e))
    saved_ini["audio"] = {"volume": str(volume), "station": str(station_num), "band": str(radio_band)}
    with open(settings.save_file, 'w') as configfile:
        saved_ini.write(configfile)
    print("Saved settings: volume: %s, station %s, band %s" % (volume, station_num, radio_band))

@atexit.register
def exit_script():
    global neopixels
    save_settings()
    pygame.mixer.quit()
    pygame.time.set_timer(settings.EVENTS['BLINK'], 0)
    if settings.PI:
        if buttonshim:
            buttonshim.set_pixel(0x00, 0x00, 0x00)
        if neopixel:
            neopixels.fill(0)
            myMotor.disable()
        if rotary:
            rotary_pixel.brightness = 0
    print("Exiting")

if __name__ == "__main__":
    run()
