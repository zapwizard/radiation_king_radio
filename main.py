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
from collections import defaultdict
import pygame
import setup
import settings
import datetime
import schedule
import ast
import json
import subprocess
import concurrent.futures
import signal
import mutagen
import serial
from copy import deepcopy
from subprocess import call
import re




#Logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Informational message")
logger.error("Error message")

# Custom signal handler for SIGINT
def signal_handler(sig, frame):
    print("CTRL + C pressed. Exiting gracefully...")
    exit_script()  # Call cleanup function
    sys.exit(0)  # Exit the script
    
# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)

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
tuning_seperation = 5
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
    pygame.mixer.init(44100, -16, 2, 8192)
    if not pygame.mixer.get_init():
        print("Error: Sound failed to initialize")
except Exception as e:
    sys.exit("Error: Sound setup failed" + str(e))

#defualt structure:
def get_default_station_data(path='', sub_folder_name='', band_name=''):
    return {
        "path": path,
        "station_name": sub_folder_name,
        "folder_name": band_name,
        "station_files": [],
        "station_ordered": False,
        "station_lengths": [],
        "total_length": 0,
        "station_start": 0
    }


def extract_number(filename):
    # Use regex to match numbers anywhere in the filename, including at the end or in parentheses
    match = re.findall(r'(\d+)', os.path.basename(filename))
    if match:
        # Convert all matched numbers to integers and return them in order
        return tuple(int(num) for num in match)
    else:
        # Return a large tuple to ensure unexpected formats are sorted last
        return (float('inf'),)



print("Startup: Starting pygame initialization")
os.environ["SDL_VIDEODRIVER"] = "dummy"  # Make a fake screen
os.environ['SDL_AUDIODRIVER'] = 'alsa'
pygame.display.set_mode((1, 1))
pygame.init()

# Reserve a channels
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
snd_error = pygame.mixer.Sound(settings.SOUND_ERROR)


# Static sound related
print("Startup: Loading static sounds (Ignore the underrun errors)")
static_sounds = {}
i = 0

# Iterate through the sorted files in the directory
for file in sorted(os.scandir(settings.STATIC_SOUNDS_FOLDER), key=lambda entry: entry.name):
    if file.name.endswith(".ogg"):  # Use file.name to access the filename
        static_sounds[i] = pygame.mixer.Sound(os.path.join("./", settings.STATIC_SOUNDS_FOLDER, file.name))
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
    except (Exception, ValueError) as error:
        saved_volume = 0.05  # Default volume
        print(f"Warning: Could not read volume setting: {error}")

    try:
        saved_band_num = int(saved_ini.get('audio', 'band'))
        print("Info: Loaded saved band:", saved_band_num)
    except (Exception, ValueError) as error:
        saved_band_num = 0  # Default band
        print(f"Warning: Could not read radio band setting: {error}")

    try:
        saved_station_num = int(saved_ini.get('audio', 'station'))
        print("Info: Loaded saved station:", saved_station_num)
    except (Exception, ValueError) as error:
        saved_station_num = 0  # Default station
        print(f"Warning: Could not read station setting: {error}")

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
        send_uart("P", "0")  # Tell the Pi Pico we are going to sleep
        if active_station:
            active_station.stop()
        pygame.mixer.Channel(2).set_volume(settings.EFFECTS_VOLUME)
        pygame.mixer.Channel(2).play(snd_off)
        save_settings()
        play_static(False)


def resume_from_standby():
    global on_off_state, motor_angle,  motor_angle_prev, volume_prev, snd_on, station_num
    if not on_off_state:
        print("Info: Resume from standby")
        pygame.time.set_timer(settings.EVENTS['BLINK'], 1000)
        on_off_state = True
        setup.uart.flushInput()

        pygame.mixer.Channel(2).set_volume(settings.EFFECTS_VOLUME)
        pygame.mixer.Channel(2).play(snd_on)

        volume_settings, station_number, radio_band_number = load_saved_settings()
        set_volume_level(volume_settings)
        print("Tuning: Loading saved station number", station_number)
        select_band(radio_band_number, get_station_pos(station_number))
        station_num = get_nearest_station(motor_angle)
        select_station(station_num, True)


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


def get_audio_length_mutagen(file_path):
    try:
        audio = mutagen.File(file_path)
        if audio is not None and hasattr(audio.info, 'length'):
            length = audio.info.length
            print(f"CACHE: {file_path}, Length: {length}")
            return length
        else:
            raise ValueError(f"Mutagen could not read duration of {file_path}")
    except Exception as e:
        print(f"ERROR: While getting duration of {file_path} with mutagen: {e}")
        return 0


def has_valid_ogg_files(path):
    return any(file.name.endswith('.ogg') for file in os.scandir(path))

def get_radio_bands(radio_folder):
    global master_start_time
    print("Startup: Starting folder search in:", radio_folder)

    if settings.RESET_CACHE:
        print("WARNING: Cache rebuilding enabled. This can take a while!")

    radio_bands = []

    for folder in sorted(os.scandir(radio_folder), key=lambda f: f.name.lower()):
        if folder.is_dir():
            print("Debug: Found band folder:", folder.name)
            sub_radio_bands = []

            for sub_folder in sorted(os.scandir(folder.path), key=lambda f: f.name.lower()):
                if sub_folder.is_dir() and has_valid_ogg_files(sub_folder.path):
                    # Set force_rebuild to True if needed
                    station_data = handle_station_folder(sub_folder, folder.name, force_rebuild=settings.RESET_CACHE)
                    if station_data:
                        sub_radio_bands.append(station_data)

            if sub_radio_bands:
                radio_bands.append({
                    "folder_name": folder.name,
                    "stations": sub_radio_bands
                })
    
    if not radio_bands:
        print("Warning: No valid radio bands found. Returning an empty list.")
    
    return radio_bands

              
                

def handle_station_folder(sub_folder, band_name, force_rebuild=False):
    path = sub_folder.path
    station_ini_file = os.path.join(path, "station.ini")
    rebuild_needed = settings.RESET_CACHE or force_rebuild or not os.path.exists(station_ini_file)
    station_data = {}

    if not rebuild_needed:
        try:
            station_ini_parser = configparser.ConfigParser()
            station_ini_parser.read(station_ini_file)
            
            if station_ini_parser.has_section('cache'):
                station_data_str = station_ini_parser.get('cache', 'station_data')
                station_data = json.loads(station_data_str)

                # Check if the current path matches the cached path
                if station_data.get("path") != path:
                    print(f"Info: Path mismatch detected for {sub_folder.name}, rebuilding cache.")
                    rebuild_needed = True

        except Exception as error:
            print(f"Error: {error}")
            rebuild_needed = True

    if rebuild_needed:
        station_data = rebuild_station_cache(path, sub_folder.name, band_name)

    return station_data






def validate_station_data(data):
    return data.get("station_files") and isinstance(data["station_files"], list) and data["station_files"]
    
def rebuild_station_cache(path, sub_folder_name, band_name):
    print(f"INFO: Starting Data Cache Rebuild for {sub_folder_name}")
    station_ini_file = os.path.join(path, "station.ini")
    station_files = glob.glob(os.path.join(path, "*.ogg"))

    if not station_files:
        print(f"Warning: No audio files found in {sub_folder_name}. Skipping station.")
        return get_default_station_data(path, sub_folder_name, band_name)

    # Sort files using the updated extract_number function
    station_files = sorted(station_files, key=extract_number)

    # Get audio lengths in parallel
    station_lengths = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(get_audio_length_mutagen, file_path): file_path for file_path in station_files}
        for future in concurrent.futures.as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                length = future.result()
                if length > 0:
                    station_lengths.append(length)
                else:
                    print(f"Warning: Invalid length for {file_path}.")
            except Exception as e:
                print(f"Failed to get length for {file_path}: {str(e)}")

    if not station_lengths:
        print(f"Warning: Could not determine lengths for any files in {sub_folder_name}. Skipping station.")
        return get_default_station_data(path, sub_folder_name, band_name)

    total_length = sum(station_lengths)

    # Read existing settings if available
    station_ini_parser = configparser.ConfigParser()
    station_data = get_default_station_data(path, sub_folder_name, band_name)

    if os.path.exists(station_ini_file):
        try:
            station_ini_parser.read(station_ini_file)
            if station_ini_parser.has_section("settings"):
                # Preserve existing settings
                station_ordered = station_ini_parser.getboolean("settings", "station_ordered", fallback=station_data["station_ordered"])
                station_start = station_ini_parser.getint("settings", "station_start", fallback=station_data["station_start"])

                # Update station_data with settings from the file
                station_data["station_ordered"] = station_ordered
                station_data["station_start"] = station_start
        except Exception as e:
            print(f"Error reading settings from station.ini for {sub_folder_name}: {str(e)}")

    # Ensure files are sorted by number if station is ordered
    if station_data["station_ordered"]:
        station_files = sorted(station_files, key=extract_number)

    # Update station_data with new values
    station_data.update({
        "station_files": station_files,
        "station_lengths": station_lengths,
        "total_length": total_length,
    })

    # Save updated station data and settings back to the ini file
    station_ini_parser["settings"] = {
        "station_ordered": str(station_data["station_ordered"]),
        "station_start": str(station_data["station_start"]),
    }
    station_ini_parser["cache"] = {
        "station_data": json.dumps(station_data, indent=4)
    }

    try:
        with open(station_ini_file, 'w') as configfile:
            station_ini_parser.write(configfile)
        print(f"Info: Cache for {sub_folder_name} rebuilt and saved successfully.")
    except Exception as e:
        print(f"Error: Failed to save cache for {sub_folder_name}: {str(e)}")

    return station_data






# Find the angular location of a radio station
def get_station_pos(station_number):
    global total_station_num
    return round(map_range(station_number,0,total_station_num - 1,settings.MOTOR_MIN_ANGLE + (settings.END_ZONE),settings.MOTOR_MAX_ANGLE - (settings.END_ZONE),),1,)


# Determine the nearest radio station to a certain motor angle
def get_nearest_station(angle):
    global tuning_seperation, total_station_num
    nearest_station = round(map_range(angle,settings.MOTOR_MIN_ANGLE + (settings.END_ZONE),settings.MOTOR_MAX_ANGLE - (settings.END_ZONE),0,total_station_num - 1,))
    #print("DEBUG: get_nearest_station, nearest_station=",nearest_station)
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
    global motor_angle, tuning_locked, tuning_prev_angle, station_num, active_station

    if motor_angle == tuning_prev_angle and not manual: # Do nothing if the angle is unchanged
        return

    nearest_station_num = get_nearest_station(motor_angle) # Find the nearest radio station to the needle position
    station_angle = get_station_pos(nearest_station_num)  # Get the exact angle of the nearest station
    range_to_station = abs(station_angle - motor_angle)  # Find the angular distance to nearest station

    # Play at volume with no static when needle is close to station position
    if range_to_station <= settings.TUNING_LOCK_ON:
        if not tuning_locked:
            tuning_volume = volume
            # print("DEBUG: Tuning: Locked to station #", nearest_station_num,
                  # "at angle:", station_angle,
                  # "Needle angle=", motor_angle,
                  # "Lock on tolerance=", settings.TUNING_LOCK_ON)
            select_station(nearest_station_num, False)
            pygame.mixer.music.set_volume(volume)
            play_static(False)
            tuning_locked = True

    # Start playing audio with static when the needle get near a station position
    elif range_to_station < settings.TUNING_NEAR:
        tuning_volume = clamp(round(volume / range_to_station, 3),settings.VOLUME_MIN,1)
        pygame.mixer.music.set_volume(tuning_volume)

        if active_station and active_station is not None:
            play_static(True)
            tuning_locked = False
            # print("DEBUG: Tuning: Lost station lock on #",
                  # nearest_station_num, "at angle:",station_angle,
                  # "Needle=",motor_angle,
                  # "Range to station =", round(range_to_station,1))
        else:
            #print("Tuning: Nearing station #", nearest_station_num, "at angle:", station_angle,"Needle=",motor_angle)
            select_station(nearest_station_num, False)

    # Stop any music and play just static if the needle is not near any station position
    else:
        if active_station and active_station is not None:
            print("Tuning: No active station. Nearest station # is:", nearest_station_num, "at angle:", station_angle,"Needle=", motor_angle, "tuning_seperation =", tuning_seperation)
            if active_station:
                active_station.stop()
            pygame.mixer.music.stop()
            active_station = None
            #station_num = None
            tuning_locked = False
            play_static(True)
    tuning_prev_angle = motor_angle
    

def next_station():
    global station_num, total_station_num

    station_num = get_nearest_station(motor_angle) + 1
    if station_num >= total_station_num:
        station_num = total_station_num - 1  # Ensure station_num does not exceed valid index range
        print(f"TUNING: At the end of the station list {station_num} / {total_station_num}")
        next_band()
    else:
        print(f"TUNING: Next station {station_num} / {total_station_num}")
    select_station(station_num, True)

def prev_station():
    global station_num, total_station_num

    station_num = get_nearest_station(motor_angle) - 1
    if station_num < 0:
        station_num = 0
        print(f"Tuning: At the beginning of the station list {station_num} / {total_station_num}")
        prev_band()
    else:
        print(f"Tuning: Previous station {station_num} / {total_station_num}")
    select_station(station_num, True)


def select_band(new_band_num, restore_angle=None):
    global radio_band, total_station_num, tuning_seperation
    global radio_band_total, station_list, stations, tuning_locked
    global active_station, volume, snd_band

    print(f"select_band: DEBUG: select_band called with new_band_num={new_band_num}, type={type(new_band_num)}")

    if not isinstance(new_band_num, int):
        print("select_band: ERROR: new_band_num must be an integer.")
        return

    if new_band_num >= radio_band_total or new_band_num < 0:
        print("select_band: ERROR: Selected an invalid band number:", new_band_num, "/", radio_band_total)
        return

    if active_station:
        active_station.stop()
        active_station = None

    radio_band = new_band_num
    print("select_band: Changing to band number", new_band_num)

    try:
        band_data = radio_band_list[new_band_num]  # Expecting a dictionary now
        if not isinstance(band_data, dict):
            raise TypeError(f"band_data is not a dictionary. Type: {type(band_data)}")

        folder_name = band_data.get("folder_name")
        folder_path = os.path.join(settings.STATIONS_ROOT_FOLDER, folder_name)
        

    except IndexError:
        print(f"select_band: IndexError: new_band_num {new_band_num} is out of the range of the radio_band_list.")
    except Exception as e:
        print("select_band: Unexpected error accessing radio_band_list:", str(e))


    # Audible Band callout
    band_callout_path = os.path.join(folder_path, "callout.ogg")  # Example file name
    if os.path.exists(band_callout_path):
        band_callout_sound = pygame.mixer.Sound(band_callout_path)
        channel = pygame.mixer.Channel(3)
        channel.play(band_callout_sound)
        channel.set_volume(volume * settings.BAND_CALLOUT_VOLUME)
        if settings.BAND_CALLOUT_WAIT:
            while channel.get_busy():  # Wait until the callout sound is finished
                time.sleep(0.1)
    else:
        print(f"select_band: ERROR: Band callout file does not exist at {band_callout_path}")


    # Play band change sound
    pygame.mixer.Channel(4).play(snd_band)
    pygame.mixer.Channel(4).set_volume(volume * settings.BAND_CHANGE_VOLUME)

    # Set the station list based on the updated structure
    station_data_list = band_data.get("stations", [])
    
    # Set the total number of stations
    total_station_num = len(station_data_list)
    tuning_seperation = round(settings.MOTOR_RANGE / total_station_num, 1)
    print("Info: Tuning angle separation =", tuning_seperation, "Number of stations:", total_station_num)

    # Initialize the stations list with RadioClass instances
    stations = []
    for station_data in station_data_list:
        if isinstance(station_data, dict):
            try:
                station = RadioClass(station_data)
                stations.append(station)
                #print(f"select_band: DEBUG: Added station '{station.label}'")
            except Exception as e:
                print(f"select_band: ERROR: Failed to initialize RadioClass for station: {station_data.get('station_name', 'Unknown')}, error: {str(e)}")
        else:
            print(f"select_band: ERROR: Expected station data to be a dictionary, got {type(station_data)} instead")
    sweep(restore_angle)

    print(f"select_band: Total stations loaded: {total_station_num}")




def select_station(new_station_num, manual=False):
    global station_num, active_station, motor_angle, tuning_locked, stations, total_station_num

    # Validate the station list
    if not stations:
        print("Warning: No stations available to select.")
        return

    # Check if the new station number is valid
    if new_station_num < 0 or new_station_num >= len(stations):
        print("Warning: Selected an invalid station number:", new_station_num, "/", len(stations) - 1)
        return

    # If the station number hasn't changed and it's not a manual tune, do nothing
    if new_station_num == station_num and not manual:
        return

    # Set motor angle if manually tuning
    if manual:
        motor_angle = get_station_pos(new_station_num)
        tuning_locked = False
        set_motor(motor_angle, True)

    # Change to the new station
    station_num = new_station_num
    active_station = stations[station_num]

    # Get the station label
    station_name = active_station.label if hasattr(active_station, 'label') else 'Unknown'

    # Log the change
    print(f"Select_Station: '{station_name}' (Station {station_num + 1} of {total_station_num}), at angle = {motor_angle}")

    # Start playback for the active station
    active_station.live_playback()


def prev_station():
    global station_num, motor_angle, total_station_num

    # Get the nearest station to the current motor angle and move to the previous one
    station_num = get_nearest_station(motor_angle) - 1

    if station_num < 0:
        station_num = 0
        print(f"Tuning: At the beginning of the station list {station_num} / {total_station_num}")
        play_error_snd()
        prev_band()
    else:
        print(f"Tuning: Previous station {station_num} / {total_station_num}")
        select_station(station_num, True)


def next_station():
    global station_num, motor_angle, total_station_num

    # Get the nearest station to the current motor angle and move to the next one
    station_num = get_nearest_station(motor_angle) + 1

    if station_num >= len(stations):
        station_num = len(stations) - 1
        print(f"Tuning: At the end of the station list {station_num} / {total_station_num}")
        play_error_snd()
        next_band()
    else:
        print(f"Tuning: Next station {station_num} / {total_station_num}")
        select_station(station_num, True)




def prev_band():
    global radio_band, radio_band_total, motor_angle
    new_band = radio_band - 1
    if new_band < 0:
        radio_band = 0
        print("Tuning: At the beginning of the band list", radio_band, "/", radio_band_total)
        play_error_snd()
    else:
        print("Tuning: Previous radio band", radio_band, "/", radio_band_total)
        select_band(new_band, motor_angle)


def next_band():
    global radio_band, radio_band_total, motor_angle
    new_band = radio_band + 1
    if new_band >= radio_band_total:
        radio_band = radio_band_total -1
        print("Tuning: At end of the band list", radio_band, "/", radio_band_total)
        play_error_snd()
    else:
        print("Tuning: Next radio band", radio_band, "/", radio_band_total)
        select_band(new_band, motor_angle)

def wait_for_pico(uart_message):
    global pico_state, heartbeat_time

    # Process the UART message if provided
    if uart_message:
        if isinstance(uart_message, list) and len(uart_message) > 1:
            try:
                process_uart_message(uart_message)
            except Exception as error:
                print("wait_for_pico: ERROR: Error in processing UART message:", str(error))
                setup.uart.close()  # Attempt to close and reset UART connection
                time.sleep(2)  # Delay before retrying
        else:
            print("wait_for_pico: DEBUG: Invalid UART message structure:", uart_message)

    # Send heartbeat if interval elapsed and we have not received a valid message
    now = time.time()
    if not pico_state and now - heartbeat_time > settings.UART_HEARTBEAT_INTERVAL:
        send_uart("H", "Zero")
        print("wait_for_pico: Waiting: Sending Heartbeat to Pico")
        blink_led()
        heartbeat_time = now


def play_error_snd():
    pygame.mixer.Channel(4).play(snd_error)
    pygame.mixer.Channel(4).set_volume(volume * settings.SOUND_ERROR_VOLUME)



def shutdown_zero():
    print("Info: Doing a full shutdown")
    call("sudo nohup shutdown -h now", shell=True)

def send_uart(command_type, data1, data2="", data3="", data4=""):
    #print(f"DEBUG: send_uart called with command_type={command_type}, data1={data1}, data2={data2}, data3={data3}, data4={data4}")
    # Debug each argument to see if they are of valid types
    if not all(isinstance(arg, (str, bytes, os.PathLike, bool, int, float)) for arg in [data1, data2, data3, data4]):
        print("ERROR: One of the data arguments is an unsupported type. Arguments must be str, bytes, os.PathLike, bool, int, or float.")
        raise TypeError("Invalid type passed to send_uart")
    # Convert booleans if necessary
    data1 = "1" if data1 is True else ("0" if data1 is False else str(data1))
    data2 = "1" if data2 is True else ("0" if data2 is False else str(data2))
    data3 = "1" if data3 is True else ("0" if data3 is False else str(data3))
    data4 = "1" if data4 is True else ("0" if data4 is False else str(data4))
    # Proceed to write the UART message
    if setup.uart:
        try:
            message = f"{command_type},{data1},{data2},{data3},{data4},\n"
            setup.uart.write(bytes(message, "utf-8"))
        except Exception as error:
            _, err, _ = sys.exc_info()
            print("ERROR: UART Output: (%s)" % err, error)

def receive_uart():
    if not setup.uart:
        return []
    if not setup.uart.is_open:
        try:
            setup.uart.open()
        except Exception as error:
            print(f"receive_uart: UART Open Error: {error} - Device might be disconnected or multiple access on port.")
            return []

    if setup.uart.in_waiting == 0:
        # If there's nothing waiting, don't try to read.
        return []

    try:
        line = setup.uart.readline()  # Read data until "\n" or timeout
        setup.uart.flush()
        if line:
            line = line.decode("utf-8").strip("\n")  # Convert from bytes to string and strip new line
            parsed_data = line.split(",")
            return parsed_data
        else:
            return []
    except serial.SerialException as error:
        print(f"receive_uart: ERROR: UART Input Error: No data received from UART. - {error} - Device might be disconnected or multiple access on port.")
        setup.uart.close()  # Close the port on error
    except Exception as error:
        print(f"receive_uart: ERROR: UART Input Error: {error}")
        setup.uart.close()  # Close the port on generic error

    return []







def midnight():
    global midnight, master_start_time, stations
    midnight_str = time.strftime("%m/%d/%Y") + " 00:00:00"
    midnight = int(time.mktime(time.strptime(midnight_str, "%m/%d/%Y %H:%M:%S")))
    master_start_time = midnight

    for station in stations:
        station.reference_time = master_start_time + station.station_offset
    print("INFO: Midnight:", str(datetime.timedelta(seconds=midnight)))

schedule.every().day.at("00:00:01").do(midnight)

def process_uart_message(uart_message):
    global pico_heartbeat_time, pico_state

    if not isinstance(uart_message, list) or not all(isinstance(item, str) for item in uart_message) or len(uart_message) <= 1:
        print("DEBUG: Invalid UART message structure:", uart_message)
        return  # Early exit if the message is not as expected

    # Direct processing based on the message type
    message_type = uart_message[0]

    if message_type == "I":
        handle_info_message(uart_message)
    elif message_type == "H":
        # Handle heartbeat message
        if uart_message[1] == "Pico":
            pico_heartbeat_time = time.time()
            pico_state = True
            #print("UART: Pi Pico heartbeat received")
    elif message_type == "B" and on_off_state:
        handle_button_message(uart_message)
    elif message_type == "V" and on_off_state:
        handle_volume_message(uart_message)
    elif message_type == "M" and on_off_state:
        handle_motor_message(uart_message)
    elif message_type == "P":
        handle_power_message(uart_message)


def handle_info_message(uart_message):
    if on_off_state:
        print("Pico serial:", uart_message)

def handle_heartbeat_message(uart_message):
    global pico_heartbeat_time, pico_state
    if uart_message[1] == "Pico":
        pico_heartbeat_time = time.time()
        pico_state = True

def handle_button_message(uart_message):
    try:
        if len(uart_message) < 3:
            print("ERROR: Missing button ID in UART message:", uart_message)
            return

        button_id = uart_message[2]
        action_type = "press" if uart_message[1] == "1" else "hold"

        # Handle the button action based on press or hold
        process_button_action(button_id, action_type=action_type)

    except IndexError as error:
        print("Button Handling Error:", str(error))


def handle_volume_message(uart_message):
    try:
        volume_level = float(uart_message[1])
        set_volume_level(volume_level)
    except (IndexError, ValueError) as error:
        print("Volume Error:", str(error))

def handle_motor_message(uart_message):
    try:
        motor_angle = float(uart_message[1])
        set_motor(motor_angle)
        #print("DEBUG: handle_motor_message, motor_angle=",motor_angle)
    except (IndexError, ValueError) as error:
        print("Motor Error:", str(error))

def handle_power_message(uart_message):
    if len(uart_message) > 1:
        action = uart_message[1]
        if action == "1":
            print("Info: Pi Pico called resume")
            resume_from_standby() if not on_off_state else send_uart("P", "On")
        elif action == "0":
            print("Info: Pi Pico called Standby")
            standby()
        elif action == "2":
            print("Info: Pi Pico called code exit")
            exit_script()
            sys.exit(0)
        elif action == "3":
            print("Info: Pi Pico called Pi Zero Shutdown")
            shutdown_zero()


def sweep(restore_angle):
    if settings.SWEEP_ENABLED:
        print("sweep, DEBUG: Sweep triggered")
        send_uart("C", "Sweep", restore_angle)
    elif restore_angle:
        print("sweep, DEBUG: Sweep Skipped")
        set_motor(restore_angle, True)
        send_uart("C", "NoSweep")


def run():
    global clock, on_off_state, snd_on, tuning_locked, restore_angle
    global motor_angle, radio_band_total, radio_band_list, heartbeat_time, pico_heartbeat_time, pico_state

    # Initial heartbeat loop until we get a successful response from Pi Pico
    print("Waiting: Waiting for Pi Pico heartbeat")
    while not pico_state:
        # Check GPIO input if available
        if setup.gpio_available:
            check_gpio_input()

        # Receive UART message once per loop iteration
        uart_message = receive_uart()

        # Pass the UART message to wait_for_pico
        wait_for_pico(uart_message)

    # Step 1: Cache all radio bands and stations
    radio_band_list = get_radio_bands(settings.STATIONS_ROOT_FOLDER)
    if not radio_band_list:
        print("ERROR: No radio bands found. Please check the folder structure and files.")
        sys.exit(1)

    # Now that bands are loaded, print how many were found
    print(f"Debug: Loaded radio bands - Total: {len(radio_band_list)}")

    # Set the total number of bands found
    radio_band_total = len(radio_band_list)

    # Step 2: Load saved settings, now that we have cached all bands and stations
    volume_settings, station_number, radio_band_number = load_saved_settings()

    # Step 3: Initialize the volume and select the saved band and station
    set_volume_level(volume_settings)
    print("Tuning: Loading saved station number", station_number)

    # After loading settings, attempt to select the saved band and station if valid
    if radio_band_number < radio_band_total and radio_band_number >= 0:
        select_band(radio_band_number, get_station_pos(station_number))
    else:
        print(f"Warning: Saved band number {radio_band_number} is invalid. Defaulting to band 0.")
        select_band(0, get_station_pos(0))

    print("****** Radiation King Radio is now running ******")
    try:
        while True:
            now = time.time()

            # Run any pending scheduled jobs
            schedule.run_pending()

            # Receive UART message
            uart_message = receive_uart()

            # Check if the Pi Pico is still sending heartbeats
            if now - pico_heartbeat_time > settings.PICO_HEARTBEAT_TIMEOUT:
                standby()
                wait_for_pico(uart_message)
                pico_heartbeat_time = now

            # Process received UART message during normal operation
            if uart_message:
                try:
                    process_uart_message(uart_message)
                except Exception as error:
                    print("ERROR: Error in processing UART message:", str(error))

            # Handle pygame events
            for event in pygame.event.get():
                handle_event(event)

            # GPIO and tuning logic
            if setup.gpio_available:
                check_gpio_input()
                
            # Radio tuning
            if on_off_state:
                tuning()

            # Send heartbeat to Pico if necessary
            if now - heartbeat_time > settings.UART_HEARTBEAT_INTERVAL:
                send_uart("H", "Zero")
                heartbeat_time = now

            clock.tick(200)
    except KeyboardInterrupt:
        print("KeyboardInterrupt received, exiting...")
        exit_script()  # Call cleanup function
        sys.exit(0)  # Ensure the script exits



def process_button_action(button_id, action_type="press"):
    """Handle both press and hold actions for buttons."""
    if not isinstance(button_id, str):
        print(f"ERROR: Button identifier should be a string, but got {type(button_id)}")
        return

    if action_type == "press":
        if button_id == "0" and active_station: active_station.rewind()
        if button_id == "1": prev_station()
        if button_id == "2":
            if active_station: active_station.play_pause()
            else: play_static(False)
        if button_id == "3": next_station()
        if button_id == "4" and active_station: active_station.fast_forward()
    elif action_type == "hold":
        if button_id == "0" and active_station: active_station.prev_song()
        if button_id == "1": prev_band()
        if button_id == "2" and active_station:
            active_station.toggle_order()  # Toggle between ordered and random
            active_station.next_song()  # Go to the next song after toggling
        if button_id == "3": next_band()
        if button_id == "4" and active_station: active_station.next_song()
    else:
        print(f"ERROR: Unknown action type {action_type} for button {button_id}")




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
        self.is_ordered = False  # Set mode to random
        print("Info: Randomized song order")

    def order_station(self):
        self.is_ordered = True

        # Reload station data from the cache
        cache_file = os.path.join(self.path, "station.ini")
        station_ini_parser = configparser.ConfigParser()

        if os.path.exists(cache_file):
            try:
                station_ini_parser.read(cache_file)
                if station_ini_parser.has_section("cache"):
                    station_data = json.loads(station_ini_parser.get("cache", "station_data"))
                    self.files = deque(station_data["station_files"])
                    self.song_lengths = deque(station_data["station_lengths"])
                    self.station_offset = station_data.get("station_start", 0)
                    print("Info: Station data reloaded from cache successfully")
            except Exception as e:
                print(f"Error loading station data from cache: {str(e)}")

        # Recalculate the playback position based on the reference time
        current_time = time.time()
        elapsed_time = current_time - (master_start_time + self.station_offset)

        # If the total station length is valid and elapsed_time is positive
        total_station_length = sum(self.song_lengths)
        if total_station_length > 0 and elapsed_time > 0:
            # Calculate the current position within the total station length
            self.position = elapsed_time % total_station_length

            # Iterate over song lengths to find the correct song and position within it
            accumulated_length = 0
            for i, length in enumerate(self.song_lengths):
                if accumulated_length + length > self.position:
                    # Rotate the deques to start from the correct song
                    self.files.rotate(-i)
                    self.song_lengths.rotate(-i)
                    # Adjust self.position to be the position within the current song
                    self.position -= accumulated_length
                    break
                accumulated_length += length

        # Reset reference_time to align with the current position
        self.reference_time = current_time - self.position

        # Use live_playback to start playing from the correct position
        self.live_playback()

        print("Info: Reloaded and ordered station from cache, restored playback position")






        
    def toggle_order(self):
        if self.is_ordered:
            self.randomize_station()
        else:
            self.order_station()

        print(f"Info: Toggled order mode. is_ordered={self.is_ordered}")

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
    def __init__(self, station_data, *args, **kwargs):
        global master_start_time

        try:
            super(RadioClass, self).__init__(*args, **kwargs)

            if not isinstance(station_data, dict):
                print("station_data=", station_data)
                raise TypeError(f"Expected station_data to be a dictionary, got {type(station_data)} instead")

            self.path = station_data.get('path', '')
            self.label = station_data.get('station_name', 'Unknown')
            self.directory = station_data.get('folder_name', 'Unknown')
            self.files = deque(station_data.get('station_files', []))
            self.ordered = station_data.get('station_ordered', False)
            self.song_lengths = deque(station_data.get('station_lengths', []))
            self.total_length = station_data.get('total_length', 0)
            self.station_offset = station_data.get('station_start', 0)
            self.reference_time = master_start_time + self.station_offset

            # Initialize is_ordered correctly based on station_ordered
            self.is_ordered = self.ordered

            print(f"Debug: Successfully initialized RadioClass for {self.label}")

        except KeyError as e:
            print(f"Error: Missing expected key in station_data: {e}")
        except Exception as e:
            print(f"Error: Exception during RadioClass initialization: {str(e)}")



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

def shutdown_sequence():
    save_settings()
    pygame.mixer.quit()
    pygame.time.set_timer(settings.EVENTS['BLINK'], 0)
    send_uart("I", "Pi Zero Shutdown")
    send_uart("P", "0")  # Tell the Pi Pico we are going to sleep
    if setup.uart:
        setup.uart.close()  # Close port
    if hasattr(setup, 'device_name') and setup.device_name:
        setup.mount.unmount(setup.mount.get_media_path(settings.PICO_FOLDER_NAME))
    print("Action: Exiting")

# Register atexit to ensure clean-up on normal exit
@atexit.register
def exit_script():
    shutdown_sequence()

# Custom signal handler for SIGINT
def signal_handler(sig, frame):
    print("CTRL + C pressed. Exiting gracefully...")
    shutdown_sequence()
    sys.exit(0)

# Register the signal handler
signal.signal(signal.SIGINT, signal_handler)




if __name__ == "__main__":
    run()
