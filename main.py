# Licence: Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) Written by ZapWizard (Joshua Driggs)

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
import setup
import settings
import datetime

# Variables
clock = pygame.time.Clock()
volume = float(0.05)
volume_time = time.time()
volume_prev = float(0.0)
station_num = int(0)
station_list = []
stations = []
total_station_num = int(0)
radio_band = int(0)
radio_band_list = []
radio_band_total = int(0)
active_station = None
led_state = True
on_off_state = False
prev_motor_angle = 0
motor_angle = 0
tuning_volume = 0
tuning_sensitivity = 5
tuning_locked = False
tuning_prev_angle = None
ADC_0_Prev_Values = []
ADC_2_Prev_Values = []
ADC_2_Prev_Value = 0
motor_angle_prev = settings.MOTOR_MIN_ANGLE
heartbeat_time = 0
pico_state = False
pico_heartbeat_time = 0

# Time related
midnight_str = time.strftime( "%m/%d/%Y" ) + " 00:00:00"
midnight = int( time.mktime( time.strptime( midnight_str, "%m/%d/%Y %H:%M:%S" ) ) )
master_start_time = midnight
print("Startup: Time:", time.strftime( "%m/%d/%Y %H:%M:%S"))
print("Startup: Midnight:", str(datetime.timedelta(seconds=midnight)))

# Sound related
try:
    print("Startup: Starting sound initialization")

    pygame.mixer.quit()
    pygame.mixer.init(44100, -16, 2, 4096)
    if not pygame.mixer.get_init():
        print("Error: Sound failed to initialize")
except Exception as e:
    sys.exit("Error: Sound setup failed" + str(e))

print("Startup: Starting pygame initialization")
os.environ["SDL_VIDEODRIVER"] = "dummy"  # Make a fake screen
os.environ['SDL_AUDIODRIVER'] = 'alsa'
pygame.display.set_mode((1, 1))
pygame.init()

# Reserve a sound channel for static sounds
print("Startup: Loading static sounds (Ignore the underrun errors)")
pygame.mixer.set_reserved(1)
pygame.mixer.set_reserved(2)
pygame.mixer.set_reserved(3)
pygame.mixer.set_reserved(4)
pygame.mixer.Channel(1)
pygame.mixer.Channel(2)
pygame.mixer.Channel(3)
pygame.mixer.Channel(4)

snd_off = pygame.mixer.Sound(settings.SOUND_OFF)
snd_on = pygame.mixer.Sound(settings.SOUND_ON)
snd_band = pygame.mixer.Sound(settings.SOUND_BAND_CHANGE)

# Static sound related
static_sounds = {}
i = 0
for file in sorted(os.listdir(settings.STATIC_SOUNDS_FOLDER)):
    if file.endswith(".ogg"):
        static_sounds[i] = pygame.mixer.Sound("./" + settings.STATIC_SOUNDS_FOLDER + "/" + file)
        i += 1
print("Info: Loaded", len(static_sounds), "static sound files")


def set_motor(angle, manual = False):  # Tell the motor controller what angle to set, used for manual tuning
    global motor_angle, tuning_locked
    motor_angle = angle
    if manual:
        send_uart("M", motor_angle)


def load_saved_settings():
    saved_ini = configparser.ConfigParser()
    # Load saved settings:
    try:
        assert os.path.exists(settings.SAVE_FILE)
        saved_ini.read(settings.SAVE_FILE, encoding=None)
    except Exception as error:
        print("Warning: While reading the following:", str(error))

    try:
        saved_volume = float(saved_ini.get('audio', 'volume'))
        print("Info: Loaded saved volume:", saved_volume)
    except Exception as error:
        saved_volume = 0.05
        print("Warning: Could not read volume setting in", str(error))

    try:
        saved_station_num = int(saved_ini.get('audio', 'station'))
        print("Info: Loaded saved station:", saved_station_num)
    except Exception as error:
        saved_station_num = 0
        print("Warning: Could not read station setting in", str(error))

    try:
        saved_band_num = int(saved_ini.get('audio', 'band'))
        print("Info: Loaded saved band:", saved_band_num)
    except Exception as error:
        saved_band_num = 0
        print("Warning: Could not read radio band setting in", str(error))
    return saved_volume, saved_station_num, saved_band_num


def map_range(x, in_min, in_max, out_min, out_max):
    if in_max <= 0 or in_max == in_min:
        in_max = in_min + 0.001
    if out_min <= out_max:
        return max(min((x-in_min) * (out_max - out_min) / (in_max-in_min) + out_min, out_max), out_min)
    else:
        return min(max((x-in_min) * (out_max - out_min) / (in_max-in_min) + out_min, out_max), out_min)


def blink_led():
    global led_state
    if not settings.DISABLE_HEARTBEAT_LED:
        if led_state:
            os.system('echo 0 | sudo dd status=none of=/sys/class/leds/led0/brightness')  # led on
            led_state = False
        else:
            os.system('echo 1 | sudo dd status=none of=/sys/class/leds/led0/brightness')  # led off
            led_state = True


def set_volume_level(volume_level, direction=None):
    global volume, volume_time, volume_prev

    if volume_level == volume_prev:
        return

    if direction == "up":
        volume_level += settings.VOLUME_STEP
    elif direction == "down":
        volume_level -= settings.VOLUME_STEP

    volume = clamp(round(float(volume_level), 3), settings.VOLUME_MIN, 1)
    pygame.mixer.music.set_volume(volume)
    if volume > 0:
        static_volume = max(round(volume * settings.STATIC_VOLUME, 3), settings.STATIC_VOLUME_MIN)
    else:
        static_volume = 0
    pygame.mixer.Channel(1).set_volume(static_volume)
    # print("Volume =", volume, "Static_volume = ", static_volume)  # Debug

    volume_time = time.time()
    return volume


def clamp(number, minimum, maximum):
    return max(min(maximum, number), minimum)


def standby():
    global on_off_state, motor_angle, motor_angle_prev, volume, snd_off
    if on_off_state:
        on_off_state = False
        print("Info: Going into standby")
        send_uart("P", False)  # Tell the Pi Pico we are going to sleep
        if active_station:
            active_station.stop()
        pygame.mixer.Channel(2).set_volume(settings.EFFECTS_VOLUME)
        pygame.mixer.Channel(2).play(snd_off)
        save_settings()
        play_static(False)


def resume_from_standby():
    global on_off_state, motor_angle,  motor_angle_prev, volume_prev, snd_on
    if not on_off_state:
        print("Info: Resume from standby")
        pygame.time.set_timer(settings.EVENTS['BLINK'], 1000)
        on_off_state = True
        setup.uart.flushInput()

        pygame.mixer.Channel(2).set_volume(settings.EFFECTS_VOLUME)
        pygame.mixer.Channel(2).play(snd_on)

        play_static(True)

        volume_settings, station_number, radio_band_number = load_saved_settings()
        set_volume_level(volume_settings)
        print("Tuning: Loading saved station number", station_number)
        play_static(False)
        select_band(radio_band_number, get_station_pos(station_number))
        if not settings.SWEEP_ENABLED:
            send_uart("C", "NoSweep")


def handle_action(action):
    print("Action:", action)
    if action == settings.GPIO_ACTIONS["power_off"]:
        save_settings()
        sys.exit("GPIO called exit")

def check_gpio_input():
    for gpio in setup.gpio_actions.keys():
        if not setup.GPIO.input(gpio):
            handle_action(setup.gpio_actions[gpio])


def handle_event(event):
    global on_off_state, active_station
    if event.type == pygame.QUIT:
        print("Event: Quit called")
        on_off_state = False
    elif event.type == settings.EVENTS['SONG_END']:
        if active_station and active_station.state == active_station.STATES['playing']:
            print("Info: Song ended, Playing next song")
            active_station.next_song()
    elif event.type == settings.EVENTS['PLAYPAUSE']:
        print("Event: Play / Pause")
        active_station.pause_play()
    elif event.type == settings.EVENTS['BLINK']:
        blink_led()
    else:
        print("Event:", event)


def get_radio_bands(station_folder):
    global master_start_time
    print("Startup: Starting folder search in :", station_folder)
    if settings.RESET_CACHE:
        print("WARNING: Caching rebuilding enabled. This can take a while")
    radio_bands = []

    for folder in sorted(os.listdir(station_folder)):
        sub_radio_bands = []
        if os.path.isdir(station_folder + folder):
            # print("Starting radio band search in :", station_folder + folder)
            for sub_folder in sorted(os.listdir(station_folder + folder)):  # Search root audio folders for sub-folders
                path = os.path.join(station_folder, folder, sub_folder)
                if os.path.isdir(path):
                    # print("Starting song search in folder:", path)
                    if len(glob.glob(path + "/*.ogg")) == 0:
                        print("Warning: No .ogg files in:", sub_folder)
                        continue

                    station_data = None
                    station_ini_parser = configparser.ConfigParser()
                    station_meta_data_file = os.path.join(path, "station.ini")
                    station_ordered = False
                    station_name = None
                    station_start = None

                    try:
                        assert os.path.exists(station_meta_data_file)
                        station_ini_parser.read(station_meta_data_file)
                    except Exception as error:
                        print("Warning: Could not read file:", station_meta_data_file, str(error))

                    try:
                        if station_ini_parser.has_option("metadata", "station_name"):
                            station_name = station_ini_parser.get('metadata', 'station_name')
                        else:
                            print("Warning: Could not find a [metadata] [station_name] section in:", station_meta_data_file)
                            station_name = folder
                    except Exception as error:
                        print("Error: Could not read station_name:", station_meta_data_file, str(error))

                    try:
                        if station_ini_parser.has_option("metadata", "ordered"):
                            station_ordered = station_ini_parser.get('metadata', 'ordered')
                        else:
                            print("Warning: Could not find a [metadata] [ordered] section in:", station_meta_data_file)
                            station_ordered = False
                    except Exception as error:
                        print("Error: Could not read ordered:", station_meta_data_file, str(error))

                    # Load the ordered and start_time and overwrite cached data to allow for tweaking those settings
                    try:
                        if station_ini_parser.has_option("metadata", "start_time"):
                            station_start= float(eval(station_ini_parser.get('metadata', 'start_time')))
                            #print("DEBUG: Station has an start time of:",str(datetime.timedelta(seconds=station_start)))
                        else:
                            print("Warning: Could not find a [metadata] [start_time] section in:", station_meta_data_file)
                            station_start = 0
                    except Exception as error:
                        print("Error: Could not read start_time:", station_meta_data_file, str(error))

                    if settings.RESET_CACHE or not station_ini_parser.has_section("cache"):
                        # print("Starting Song Data Cache in ", sub_folder)
                        station_files = []  # File paths
                        station_lengths = []  # Song lengths

                        for song_file in sorted(os.listdir(path)):
                            if song_file.endswith(".ogg"):
                                station_files.append(os.path.join(path, song_file))
                                file_path = os.path.join(path, song_file)
                                try:
                                    station_lengths.append(mutagen.File(file_path).info.length)
                                except Exception as error:
                                    print("Mutagen error:", str(error), "in file", song_file)
                        total_length = sum(station_lengths)

                        if not station_ordered:
                            # Randomized based on the nearest 10 minutes to allow two radios to sync up
                            seed = round(time.time() / 600)
                            random.Random(seed).shuffle(station_files)
                            random.Random(seed).shuffle(station_lengths)
                            # print("randomizing", folder)

                        if not station_data:
                            station_data = [station_name, folder, station_files, station_ordered, station_lengths,
                                            total_length, station_start]
                            station_data = list(station_data)

                            try:
                                station_ini_parser.read(station_meta_data_file, encoding=None)
                                if not station_ini_parser.has_section("cache"):
                                    station_ini_parser.add_section("cache")
                                    print("Info: Adding the Cache section to", station_meta_data_file)
                                # else:
                                # print("There is already a cache section in", station_meta_data_file)
                            except Exception as error:
                                print(str(error), "in", station_meta_data_file)

                            station_ini_file = None
                            try:
                                station_ini_file = open(station_meta_data_file, 'w')
                            except Exception as error:
                                print("Warning: Failed to open cache file", station_meta_data_file, "|", str(error))

                            try:
                                station_ini_parser.set("cache", "station_data", str(station_data))
                                station_ini_parser.write(station_ini_file)
                                print("Info: Saved Cache to %s, station %s" % (station_meta_data_file, station_name))
                                station_ini_file.close()
                            except Exception as error:
                                print("Error: Failed to save cache to", station_meta_data_file, "/", str(error))
                    else:
                        try:
                            station_data = list(eval(station_ini_parser.get('cache', 'station_data')))
                            station_data[3] = station_ordered
                            station_data[6] = station_start
                            print("Info: Loaded data from", station_meta_data_file, "Ordered=",station_data[3],"start_time=",station_data[6])
                        except Exception as error:
                            print(str(error), "Error: Could not read cache file in", station_meta_data_file)

                        try:
                            if not eval(str(station_data[3])):  # Randomized cached stations
                                # Randomized based on the nearest 10 minutes to allow two radios to sync up
                                seed = round(time.time() / 600)
                                random.Random(seed).shuffle(station_data[2])  # station_files
                                random.Random(seed).shuffle(station_data[4])  # station_lengths
                                # print("randomizing", folder)
                        except Exception as error:
                            print(str(error), "station_data[3]=",station_data[3])

                    # print("Loading station:", station_name, "Ordered =", station_ordered, station_start)

                    if len(station_data) > 0:
                        sub_radio_bands.append(station_data)

        if sub_radio_bands:
            radio_bands.append(sub_radio_bands)
    return radio_bands


# Find the angular location of a radio station
def get_station_pos(station_number):
    global total_station_num, tuning_sensitivity
    return round(map_range(station_number,0,total_station_num - 1,settings.MOTOR_MIN_ANGLE + (tuning_sensitivity),settings.MOTOR_MAX_ANGLE - (tuning_sensitivity),),1,)


# Determine the nearest radio station to a certain motor angle
def get_nearest_station(angle):
    global tuning_sensitivity, total_station_num
    nearest_station = round(map_range(angle,settings.MOTOR_MIN_ANGLE + (tuning_sensitivity),settings.MOTOR_MAX_ANGLE - (tuning_sensitivity),0,total_station_num - 1,))
    if nearest_station >= total_station_num:
        nearest_station = total_station_num - 1
    return nearest_station


# Play a random bit of static
def play_static(play):
    global static_sounds, volume
    if play:
        if not pygame.mixer.Channel(1).get_busy():
            random_snd = random.randrange(0, len(static_sounds) - 1)
            pygame.mixer.Channel(1).play(static_sounds[random_snd])
            if volume > 0:
                pygame.mixer.Channel(1).set_volume(
                    max(round(volume * settings.STATIC_VOLUME, 3), settings.STATIC_VOLUME_MIN))
            else:
                pygame.mixer.Channel(1).set_volume(0)
    else:
        pygame.mixer.Channel(1).stop()


# Tune into a station based on the motor angle
def tuning(manual=False):
    global motor_angle, volume, static_sounds, tuning_locked, tuning_prev_angle
    global active_station, tuning_volume, tuning_sensitivity, station_num

    #if motor_angle == tuning_prev_angle and not manual: # Do nothing if the angle is unchanged
    #    return

    nearest_station_num = get_nearest_station(motor_angle) # Find the nearest radio station to the needle position
    station_angle = get_station_pos(nearest_station_num)  # Get the exact angle of that station
    range_to_station = abs(station_angle - motor_angle)  # Find the angular distance to nearest station
    lock_on_tolerance = round(tuning_sensitivity / settings.TUNING_LOCK_ON, 1)

    # Play at volume with no static when needle is close to station position
    if range_to_station <= lock_on_tolerance:
        if not tuning_locked:
            tuning_volume = volume
            #print("Tuning: Locked to station #", nearest_station_num,
            #      "at angle:", station_angle,
            #      "Needle angle=", motor_angle,
            #      "Lock on tolerance=", lock_on_tolerance)
            select_station(nearest_station_num, False)
            pygame.mixer.music.set_volume(volume)
            play_static(False)
            tuning_locked = True

    # Start playing audio with static when the needle get near a station position
    elif range_to_station < tuning_sensitivity / settings.TUNING_NEAR:
        tuning_volume = clamp(round(volume / range_to_station, 3),settings.VOLUME_MIN,1)
        pygame.mixer.music.set_volume(tuning_volume)

        if active_station and active_station is not None:
            play_static(True)
            tuning_locked = False
            #print("Tuning: Lost station lock on #",
            #      nearest_station_num, "at angle:",station_angle,
            #      "Needle=",motor_angle,
            #      "Range to station =", range_to_station)
        else:
            #print("Tuning: Nearing station #", nearest_station_num, "at angle:", station_angle,
            #      "Needle=",motor_angle)
            select_station(nearest_station_num, False)

    # Stop any music and play just static if the needle is not near any station position
    else:
        if active_station and active_station is not None:
            #print("Tuning: No active station. Nearest station # is:", nearest_station_num, "at angle:", station_angle,"Needle=", motor_angle, "tuning_sensitivity =", tuning_sensitivity)
            if active_station:
                active_station.stop()
            pygame.mixer.music.stop()
            active_station = None
            station_num = None
            tuning_locked = False
        play_static(True)
    tuning_prev_angle = motor_angle


def select_station(new_station_num, manual=False):
    global station_num, active_station, total_station_num, motor_angle, tuning_locked, stations
    if new_station_num == station_num and not manual: # Do nothing if the station number doesn't change
        return
    if new_station_num > total_station_num or new_station_num < 0:
        print("Warning: Selected an invalid station number:", new_station_num, "/", total_station_num)
    else:
        if manual:
            motor_angle = get_station_pos(new_station_num)
            tuning_locked = False
            set_motor(motor_angle, True)

        active_station = stations[new_station_num]
        station_num = new_station_num
        print("Select_Station: Changing to station", new_station_num, active_station.label, ", Offset:",active_station.station_offset)
        active_station.live_playback()
        print("Station Position:",str(datetime.timedelta(seconds=active_station.position)))


def prev_station():
    global station_num, total_station_num, motor_angle
    station_num = get_nearest_station(motor_angle) - 1
    if station_num < 0:
        station_num = 0
        print("Tuning: At the beginning of the station list", station_num, "/", total_station_num)
        prev_band()
    else:
        print("Tuning: Previous station", station_num, "/", total_station_num)
    select_station(station_num, True)


def next_station():
    global station_num, total_station_num, motor_angle
    station_num = get_nearest_station(motor_angle) + 1
    if station_num > total_station_num - 1:
        station_num = total_station_num - 1
        print("Tuning: At end of the station list", station_num, "/", total_station_num)
        next_band()
    else:
        print("Tuning: Next station", station_num, "/", total_station_num)
    select_station(station_num, True)


def select_band(new_band_num, restore_angle = None):
    global radio_band_list, radio_band, total_station_num, tuning_sensitivity, radio_band_total, station_list
    global stations, tuning_locked, active_station, volume, snd_band

    if new_band_num > radio_band_total or new_band_num < 0:
        print("Tuning: Selected an invalid band number:", new_band_num, "/", radio_band_total)
    else:
        if active_station:
            active_station.stop()
            active_station = None
        print("Tuning: Changing to band number", new_band_num)
        radio_band = new_band_num

        pygame.mixer.Channel(4).play(snd_band)
        pygame.mixer.Channel(4).set_volume(volume / settings.BAND_CHANGE_VOLUME)

        station_list = radio_band_list[new_band_num]
        total_station_num = len(station_list)
        tuning_sensitivity = round(settings.MOTOR_RANGE / total_station_num, 1)
        print("Info: Tuning angle separation =", tuning_sensitivity, "Number of stations:", total_station_num)

        stations = []
        for radio_station in station_list:
            station_folder = radio_station[1] + "/"
            station_name = radio_station[0]
            stations.append(RadioClass(station_name, station_folder, radio_station))

        if settings.SWEEP_ENABLED:
            led_num = round(map_range(new_band_num, 0, total_station_num, settings.GAUGE_PIXEL_QUANTITY, 0))
            send_uart("C", "Gauge", str(led_num), 1)
            time.sleep(0.3)  # Give the and LED time to show
            send_uart("C", "Sweep", restore_angle)
        elif restore_angle:
            set_motor(restore_angle, True)
            send_uart("C", "NoSweep")
        tuning(True)


def prev_band():
    global radio_band, radio_band_total, motor_angle
    new_band = radio_band - 1
    if new_band < 0:
        radio_band = 0
        print("Tuning: At the beginning of the band list", radio_band, "/", radio_band_total)
    else:
        print("Tuning: Previous radio band", radio_band, "/", radio_band_total)
        select_band(new_band, motor_angle)


def next_band():
    global radio_band, radio_band_total, motor_angle
    new_band = radio_band + 1
    if new_band > radio_band_total:
        radio_band = radio_band_total
        print("Tuning: At end of the band list", radio_band, "/", radio_band_total)
    else:
        print("Tuning: Next radio band", radio_band, "/", radio_band_total)
        select_band(new_band, motor_angle)

def wait_for_pico():
    global pico_state, heartbeat_time
    print("Waiting: Waiting for Pi Pico heartbeat")
    while not pico_state:
        if setup.gpio_available:
            check_gpio_input()
        now = time.time()
        if now - heartbeat_time > settings.UART_HEARTBEAT_INTERVAL:
            send_uart("H", "Zero")
            print("Waiting: Sending Heartbeat to Pico")
            blink_led()
            heartbeat_time = now
            uart_message = receive_uart()
        if uart_message:
            #print("UART:", uart_message)
            try:
                if uart_message[0] == "H":
                    if len(uart_message) > 1 and uart_message[1] and uart_message[1] == "Pico":
                        pico_state = True
                        print("UART: Pi Pico heartbeat received")
                if uart_message[0] == "P":
                    if uart_message[1] == "2":
                        print("UART Info: Pi Pico called code exit")
                        sys.exit()
                    if uart_message[1] == "3":
                        print("UART Info: Pi Pico called Pi Zero Shutdown")
                        shutdown_zero()

            except Exception as error:
                print("ERROR: UART:", error)

def shutdown_zero():
    print("Info: Doing a full shutdown")
    from subprocess import call
    call("sudo nohup shutdown -h now", shell=True)

def send_uart(command_type, data1, data2 = "", data3 = "", data4 = ""):
    if setup.uart:
        if not setup.uart.is_open:
            print("ERROR: UART is not open")
            return
        try:
            #print("Message:","<",command_type,",",data1,",",data2,",",data3,",",data4,",>")  # Debug (Slow)
            setup.uart.write(bytes(f"{command_type},{data1},{data2},{data3},{data4},\n","utf-8"))
        except Exception as error:
            _, err, _ = sys.exc_info()
            print("ERROR: UART: (%s)" % err, error)


def receive_uart():
    if not setup.uart:
        return
    if not setup.uart.is_open:
        try:
            setup.uart.open()
        except Exception as error:
            print("UART Open Error:", error)
        return
    try:
        line = setup.uart.readline() # Read data until "\n" or timeout
        if line:
            line = line.decode("utf-8") # Convert from bytes to string
            line = line.strip("\n") # Strip end line
            return "".join(line).split(",")
    except Exception as error:
        setup.uart.close()  # close port
        print("UART Error:",error)


def run():
    global clock, on_off_state, snd_on, on_off_state, tuning_locked
    global motor_angle, radio_band_total, radio_band_list, heartbeat_time, pico_heartbeat_time, pico_state

    radio_band_list = get_radio_bands(settings.STATIONS_ROOT_FOLDER)
    radio_band_total = len(radio_band_list) - 1

    wait_for_pico() # Wait for the pi pico heartbeat

    print("****** Radiation King Radio is now running ******")
    try:
        while True:
            now = time.time()

            if now - pico_heartbeat_time > settings.PICO_HEARTBEAT_TIMEOUT:
                standby()
                wait_for_pico()
                pico_heartbeat_time = now

            for event in pygame.event.get():
                handle_event(event)
            try:
                uart_message = receive_uart()
                if uart_message and len(uart_message) > 1:
                    #print("From UART:", uart_message)
                    # Information output
                    if uart_message[0] == "I" and on_off_state:
                        print("Pico serial:", uart_message, end="\n")

                    if uart_message[0] == "H" and uart_message[1] == "Pico":
                        pico_heartbeat_time = now
                        pico_state = True
                        #print("UART: Pi Pico heartbeat received")

                    #Button Input
                    if on_off_state:
                        if uart_message[0] == "B":
                            if uart_message[1] == "1":  # Button released
                                process_button_press(uart_message)
                            if uart_message[1] == "2":  # Button held
                                process_button_hold(uart_message)

                        #Volume Input
                        if uart_message[0] == "V":
                            set_volume_level(float(uart_message[1]))

                        #Motor input
                        if uart_message[0] == "M":
                            set_motor(float(uart_message[1]))
                            #print("From Pico: Motor command",float(uart_message[1]))

                    # Power State
                    if uart_message[0] == "P":
                        if uart_message[1] == "1":
                            print("UART Info: Pi Pico called resume")
                            if on_off_state:
                                send_uart("P","On")
                            else:
                                resume_from_standby()
                        if uart_message[1] == "0":
                            print("UART Info: Pi Pico called Standby")
                            standby()
                        if uart_message[1] == "2":
                            print("UART Info: Pi Pico called code exit")
                            sys.exit()
                        if uart_message[1] == "3":
                            print("UART Info: Pi Pico called Pi Zero Shutdown")
                            shutdown_zero()

            except Exception as error:
                   print("UART Error:", str(error))
            if setup.gpio_available:
                check_gpio_input()
            if on_off_state:
                tuning()

            if now - heartbeat_time > settings.UART_HEARTBEAT_INTERVAL:
                send_uart("H", "Zero")
                heartbeat_time = now

            clock.tick(200)
    except KeyboardInterrupt:
        sys.exit()

def process_button_press(uart_message):
    print("UART: Released button", uart_message[2])
    if uart_message[2] == "0" and active_station: active_station.rewind()
    if uart_message[2] == "1": prev_station()
    if uart_message[2] == "2" and active_station:
        active_station.play_pause()
    if uart_message[2] == "3": next_station()
    if uart_message[2] == "4" and active_station: active_station.fast_forward()


def process_button_hold(uart_message):
    print("UART: Held button", uart_message[2])
    if uart_message[2] == "0" and active_station: active_station.prev_song()
    if uart_message[2] == "1": prev_band()
    if uart_message[2] == "2" and active_station:
        active_station.randomize_station()
        active_station.next_song()
    if uart_message[2] == "3": next_band()
    if uart_message[2] == "4" and active_station: active_station.next_song()


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
        self.last_filename = None
        self.reference_time = 0
        self.position = 0 # Variable with the current position in seconds of the station
        self.sum_of_song_lengths = 0
        self.station_angle = 0
        self.last_play_position = 0
        self.last_playtime = 0
        self.station_offset = 0
        pygame.mixer.music.set_endevent(settings.EVENTS['SONG_END'])

    def live_playback(self):
        global volume
        if self.files:

            #Update position based on time that has passed
            self.position = time.time() - self.reference_time

            #  Subtract time until we are below the station length
            if self.station_length and self.position > self.station_length:
                print("Info: position:",round(self.position, 3),"longer than station length:",round(self.song_length, 3))
                while self.position > self.station_length:
                    print("Info: Looping station list")
                    self.position = self.position - self.station_length

            #  Find where in the station list we should be base on start position
            self.song_length = self.song_lengths[0]  # length of the current song
            if self.song_length and self.position > self.song_length:
                print("Info: Position:",round(self.position, 3),"is longer than the song length:",round(self.song_length, 3),"skipping ahead")

                #  Skip ahead until we reach the correct time
                while self.position > self.song_length:
                    self.files.rotate(-1)
                    self.song_lengths.rotate(-1)
                    self.position = self.position - self.song_length
                    self.song_length = self.song_lengths[0]
                self.reference_time = time.time() - self.position

            self.filename = self.files[0]
            song = self.filename

            pygame.mixer.music.load(song)
            try:
                pygame.mixer.music.play(0, self.position)
            except:
                pygame.mixer.music.play(0, 0)
            pygame.mixer.music.set_volume(volume)

            self.state = self.STATES['playing']


    def play(self):
        if self.state == self.STATES['paused']:
            pygame.mixer.music.unpause()
            self.state = self.STATES['playing']
        else:
            self.live_playback()
        print("Event: Music resumed")


    def play_pause(self):
        # print("Event: Play/pause triggered")
        if not pygame.mixer.music.get_busy():
            self.play()
        else:
            self.pause()

    def pause(self):
        self.state = self.STATES['paused']
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.state = self.STATES['paused']
            play_static(False)
        print("Action: Music paused")


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
        global volume
        self.files.rotate(-1)
        self.song_lengths.rotate(-1)
        self.reference_time = time.time()
        self.position = 0
        self.filename = self.files[0]
        song = self.filename

        print("Info: Playing next song =", self.filename,
              "length =", str(round(self.song_lengths[0], 2)),
              "position =", str(round(self.position, 2))
              )
        pygame.mixer.music.load(song)
        try:
            pygame.mixer.music.play(0, self.position)
        except:
            pygame.mixer.music.play(0, 0)
        pygame.mixer.music.set_volume(volume)
        self.state = self.STATES['playing']


    def prev_song(self):
        self.files.rotate(1)
        self.song_lengths.rotate(1)
        self.reference_time = time.time()
        self.position = 0
        self.live_playback()
        print("Action: Prev song")

    def randomize_station(self):
        seed = time.time() # Using time to shuffle the stations allows two radios to be in sync, but still randomized.
        random.Random(seed).shuffle(self.files)
        random.Random(seed).shuffle(self.song_lengths)
        print("Info: Randomized song order")


    def fast_forward(self):
        global master_start_time
        self.reference_time = self.reference_time - settings.FAST_FORWARD_INCREMENT
        if self.reference_time < master_start_time:
            master_start_time = self.position
        print("Action: Fast forward", settings.FAST_FORWARD_INCREMENT, self.reference_time, master_start_time)
        self.live_playback()


    def rewind(self):
        global master_start_time
        self.reference_time = max(self.reference_time + settings.REWIND_INCREMENT, master_start_time)
        print("Action: Rewind", settings.REWIND_INCREMENT, self.reference_time, master_start_time)
        self.live_playback()

class RadioClass(Radiostation):
    def __init__(self, station_name, station_folder, station_data, *args, **kwargs):
        global master_start_time
        # self.station_data = [folder, station_name, station_files, station_ordered, station_lengths]
        super(RadioClass, self).__init__(self, *args, **kwargs)
        self.label = station_name
        self.directory = station_folder
        self.files = deque(station_data[2])
        self.song_lengths = deque(station_data[4])
        self.total_length = station_data[5]
        self.station_offset = station_data[6]
        self.reference_time = master_start_time + self.station_offset

def save_settings():
    global volume, radio_band, station_num
    saved_ini = configparser.ConfigParser()
    try:
        assert os.path.exists(settings.SAVE_FILE)
        saved_ini.read(settings.SAVE_FILE)
    except Exception as error:
        print("Warning: Error reading the following:", str(error))
    saved_ini["audio"] = {"volume": str(volume), "station": str(station_num), "band": str(radio_band)}
    with open(settings.SAVE_FILE, 'w') as configfile:
        saved_ini.write(configfile)
    print("Info: Saved settings: volume: %s, station %s, band %s" % (volume, station_num, radio_band))

@atexit.register
def exit_script():
    save_settings()
    pygame.mixer.quit()
    pygame.time.set_timer(settings.EVENTS['BLINK'], 0)
    send_uart("I","Pi Zero Shutdown")
    send_uart("P", False)  # Tell the Pi Pico we are going to sleep
    if setup.uart:
        setup.uart.close()  # close port
    if setup.device_name:
        setup.mount.unmount(setup.mount.get_media_path(settings.PICO_FOLDER_NAME))
    print("Action: Exiting")

if __name__ == "__main__":
    run()
