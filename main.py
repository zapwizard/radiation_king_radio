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
master_start_time = time.time()
prev_motor_angle = 0
motor_angle = 0
tuning_volume = 0
tuning_sensitivity = 5
tuning_locked = False
tuning_prev_angle = None
ADC_0_Prev_Values = []
ADC_2_Prev_Values = []
ADC_2_Prev_Value = 0
motor_angle_prev = settings.motor_min_angle

try:
    print("State: Starting sound initialization")

    pygame.mixer.quit()
    pygame.mixer.init(44100, -16, 2, 4096)
    if pygame.mixer.get_init():
        print("Success: Sound initialized")
    else:
        print("Error: Sound failed to initialize")
except Exception as e:
    sys.exit("Error: Sound setup failed" + str(e))

print("State: Starting pygame initialization")
os.environ["SDL_VIDEODRIVER"] = "dummy"  # Make a fake screen
os.environ['SDL_AUDIODRIVER'] = 'alsa'
pygame.display.set_mode((1, 1))
pygame.init()

# Reserve a sound channel for static sounds
print("State: Loading static sounds (Ignore the underrun errors)")
pygame.mixer.set_reserved(1)
pygame.mixer.set_reserved(2)
pygame.mixer.Channel(1)
pygame.mixer.Channel(2)

snd_off = pygame.mixer.Sound(settings.sound_off)
snd_on = pygame.mixer.Sound(settings.sound_on)
snd_band = pygame.mixer.Sound(settings.sound_band_change)

static_sounds = {}
i = 0
for file in sorted(os.listdir(settings.static_sound_folder)):
    if file.endswith(".ogg"):
        static_sounds[i] = pygame.mixer.Sound("./" + settings.static_sound_folder + "/" + file)
        i += 1
print("Info: Loaded", len(static_sounds), "static sound files")

def Set_motor(angle):  # Tell the motor controller what angle to set, used for manual tuning
    global motor_angle
    motor_angle = angle
    send_uart("M", motor_angle)

def load_saved_settings():
    saved_ini = configparser.ConfigParser()
    # Load saved settings:
    try:
        assert os.path.exists(settings.save_file)
        saved_ini.read(settings.save_file, encoding=None)
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
    if out_min <= out_max:
        return max(min((x-in_min) * (out_max - out_min) / (in_max-in_min) + out_min, out_max), out_min)
    else:
        return min(max((x-in_min) * (out_max - out_min) / (in_max-in_min) + out_min, out_max), out_min)


def blink_led():
    global led_state
    if led_state:
        setup.GPIO.output(16, setup.GPIO.LOW)
        led_state = False
    else:
        setup.GPIO.output(16, setup.GPIO.HIGH)
        led_state = True

def set_volume_level(volume_level, direction=None):
    global volume, volume_time, volume_prev

    if volume_level == volume_prev:
        return

    if direction == "up":
        volume_level += settings.volume_step
    elif direction == "down":
        volume_level -= settings.volume_step

    volume = clamp(round(float(volume_level), 3), settings.volume_min, 1)
    pygame.mixer.music.set_volume(volume)
    if volume > 0:
        static_volume = max(round(volume / settings.static_volume,3), settings.static_volume_min)
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
        pygame.mixer.Channel(2).set_volume(settings.effects_volume)
        pygame.mixer.Channel(2).play(snd_off)
        save_settings()
        play_static(False)

def resume_from_standby():
    global on_off_state, motor_angle,  motor_angle_prev, volume_prev, snd_on
    if not on_off_state:
        print("Info: Resume from standby")
        pygame.time.set_timer(settings.EVENTS['BLINK'], 1000)
        on_off_state = True

        send_uart("C", True) # Tell the Pi Pico we are awake

        pygame.mixer.Channel(2).set_volume(settings.effects_volume)
        pygame.mixer.Channel(2).play(snd_on)

        play_static(True)

        volume_settings, station_number, radio_band_number = load_saved_settings()
        set_volume_level(volume_settings)
        select_band(radio_band_number)
        time.sleep(1.5) # Wait for the sweep effect

        select_station(station_number, True)
        #volume_prev = volume_settings
        #if active_station:
        #    active_station.live_playback()
        #    volume_settings = 0
        #    set_volume_level(volume_settings)
        #while volume_settings < volume_prev:
        #    volume_settings += settings.volume_step
        #    set_volume_level(volume_settings)
        #    time.sleep(0.05)
        play_static(False)


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
    print("State: Starting folder search in :", station_folder)

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

                    try:
                        assert os.path.exists(station_meta_data_file)
                        station_ini_parser.read(station_meta_data_file)
                    except Exception as error:
                        print("Warning: Could not read:", station_meta_data_file, str(error))

                    station_ordered = False
                    station_name = None
                    try:
                        if station_ini_parser.has_section("metadata"):
                            station_name = station_ini_parser.get('metadata', 'station_name')
                            station_ordered = eval(station_ini_parser.get('metadata', 'ordered'))
                            # print("Loading station:", station_name, "Ordered =", station_ordered)
                        else:
                            print("Warning: Could not find a [metadata] section in:", station_meta_data_file)
                            station_name = folder
                            station_ordered = True
                    except Exception as error:
                        print("Error: Could not read:", station_meta_data_file, str(error))

                    if not settings.reset_cache:
                        try:
                            station_data = eval(station_ini_parser.get('cache', 'station_data'))
                            print("Info: Loaded station data from", station_meta_data_file)
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
                            # Randomized based on the nearest 10 minutes to allow two radios to sync up
                            seed = round(time.time() / 600)
                            random.Random(seed).shuffle(station_files)
                            random.Random(seed).shuffle(station_lengths)
                            # print("randomizing", folder)

                        if not station_data:
                            station_data = station_name, folder, station_files, station_ordered, station_lengths, total_length

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
                    if len(station_data) > 0:
                        sub_radio_bands.append(station_data)
        if sub_radio_bands:
            radio_bands.append(sub_radio_bands)
    return radio_bands


# Find the angle address of a radio station
def get_station_pos(station_number):
    global total_station_num, tuning_sensitivity
    return round(
        map_range(
            station_number,
            0,
            total_station_num - 1,
            settings.motor_min_angle + (tuning_sensitivity / settings.tuning_near),
            settings.motor_max_angle - (tuning_sensitivity / settings.tuning_near),
        ),
        2,
    )


# Determine the nearest radio station to a certain motor angle
def get_nearest_station(angle):
    global tuning_sensitivity, total_station_num
    nearest_station = round(
        map_range(
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

# Play a random bit of static
def play_static(play):
    global static_sounds, volume
    if play:
        if not pygame.mixer.Channel(1).get_busy():
            random_snd = random.randrange(0, len(static_sounds) - 1)
            pygame.mixer.Channel(1).play(static_sounds[random_snd])
            if volume > 0:
                pygame.mixer.Channel(1).set_volume(
                    max(round(volume / settings.static_volume, 3), settings.static_volume_min))
            else:
                pygame.mixer.Channel(1).set_volume(0)
    else:
        pygame.mixer.Channel(1).stop()

# Tune into a station based on the motor angle
def tuning():
    global motor_angle, volume, static_sounds, tuning_locked, tuning_prev_angle
    global active_station, tuning_volume, tuning_sensitivity, station_num

    nearest_station_num = get_nearest_station(motor_angle) # Find the nearest radio station to the needle position
    station_position = get_station_pos(nearest_station_num)  # Get the exact angle of that station
    range_to_station = abs(station_position - motor_angle)  # Find the angular distance to nearest station
    lock_on_tolerance = round(tuning_sensitivity / settings.tuning_lock_on, 3)

    # Play at volume with no static when needle is close to station position
    if range_to_station <= lock_on_tolerance:
        tuning_volume = volume
        if not tuning_locked:
            if active_station:
                if nearest_station_num != station_num:
                    print("Tuning: nearest_station_num",nearest_station_num,"!=",station_num)
                    select_station(nearest_station_num, True)
                print("Tuning: Locked to station #", nearest_station_num,
                      "at angle:", station_position,
                      "Needle angle=", motor_angle,
                      "Lock on tolerance=", lock_on_tolerance)
                pygame.mixer.music.set_volume(volume)
            play_static(False)
            tuning_locked = True

    # Start playing audio with static when the needle get near a station position
    elif lock_on_tolerance < range_to_station < tuning_sensitivity / settings.tuning_near:
        tuning_volume = round(volume / range_to_station, 3)
        pygame.mixer.music.set_volume(tuning_volume)

        if active_station and active_station is not None:
            play_static(True)
            tuning_locked = False
        else:
            print("Tuning: Nearing station #", nearest_station_num, "at angle:", station_position, "Needle=",
                  motor_angle, "Near tolerance =", lock_on_tolerance)
            select_station(nearest_station_num, False)

    # Stop any music and play just static if the needle is not near any station position
    else:
        if active_station and active_station is not None:
            print("Tuning: No active station. Nearest station # is:", nearest_station_num, "at angle:", station_position,
                  "Needle=", motor_angle, "tuning_sensitivity =", tuning_sensitivity)
            if active_station:
                active_station.stop()
            pygame.mixer.music.stop()
            active_station = None
            station_num = None
            tuning_locked = False
        play_static(True)

def select_station(new_station_num, manual=False):
    global station_num, active_station, total_station_num, motor_angle, tuning_locked, stations
    if new_station_num > total_station_num or new_station_num < 0:
        print("Warning: Selected an invalid station number:", new_station_num, "/", total_station_num)
    else:
        if manual:
            motor_angle = get_station_pos(new_station_num)
            tuning_locked = False
            Set_motor(motor_angle)
            send_uart("M", motor_angle)

        if active_station and station_num != new_station_num:
            active_station.stop()

        print("Tuning: Changing to station number", new_station_num, "at angle =", motor_angle)
        active_station = stations[new_station_num]
        station_num = new_station_num
        active_station.live_playback()

def prev_station():
    global station_num, total_station_num
    station_num = station_num - 1
    if station_num < 0:
        station_num = 0
        print("Tuning: At the beginning of the station list", station_num, "/", total_station_num)
    else:
        print("Tuning: Previous station", station_num, "/", total_station_num)
    select_station(station_num, True)


def next_station():
    global station_num, total_station_num
    station_num = station_num + 1
    if station_num > total_station_num - 1:
        station_num = total_station_num - 1
        print("Tuning: At end of the station list", station_num, "/", total_station_num)
    else:
        print("Tuning: Next station", station_num, "/", total_station_num)
    select_station(station_num, True)


def select_band(new_band_num):
    global radio_band_list, radio_band, total_station_num, tuning_sensitivity, radio_band_total, station_list
    global stations, motor_angle, tuning_locked, active_station, volume, motor_angle_prev, snd_band

    if new_band_num > radio_band_total or new_band_num < 0:
        print("Tuning: Selected an invalid band number:", new_band_num, "/", radio_band_total)
    else:
        if active_station:
            active_station.stop()
            active_station = None
        print("Tuning: Changing to band number", new_band_num)
        radio_band = new_band_num

        pygame.mixer.Channel(2).play(snd_band)
        pygame.mixer.Channel(2).set_volume(volume / settings.band_change_volume)

        station_list = radio_band_list[new_band_num]
        total_station_num = len(station_list)
        tuning_sensitivity = round(settings.motor_steps / total_station_num, 3)
        print("Info: Tuning angle separation =", tuning_sensitivity, "Number of stations:", total_station_num)

        stations = []
        for radio_station in station_list:
            station_folder = radio_station[1] + "/"
            station_name = radio_station[0]
            stations.append(RadioClass(station_name, station_folder, radio_station))

        led_num = round(map_range(new_band_num,0,total_station_num,settings.led_qty,0))
        send_uart("C", "light_led", str(led_num))
        send_uart("C", "Sweep")


def prev_band():
    global radio_band, radio_band_total
    new_band = radio_band - 1
    if new_band < 0:
        radio_band = 0
        print("Tuning: At the beginning of the band list", radio_band, "/", radio_band_total)
    else:
        print("Tuning: Previous radio band", radio_band, "/", radio_band_total)
        select_band(new_band)


def next_band():
    global radio_band, radio_band_total
    new_band = radio_band + 1
    if new_band > radio_band_total:
        radio_band = radio_band_total
        print("Tuning: At end of the band list", radio_band, "/", radio_band_total)
    else:
        print("Tuning: Next radio band", radio_band, "/", radio_band_total)
        select_band(new_band)

def send_uart(command_type, data1, data2 = "", data3 = "", data4 = ""):
    if setup.uart:
        if not setup.uart.is_open:
            return
        try:
            #print("Message:","<",command_type,",",data1,",",data2,",",data3,",",data4,",>")  # Debug (Slow)
            setup.uart.write(bytes(f"{command_type},{data1},{data2},{data3},{data4},\n","utf-8"))
        except Exception as error:
            _, err, _ = sys.exc_info()
            print("UART Error: (%s)" % err, error)


def receive_uart():
    if not setup.uart:
        return
    if not setup.uart.is_open:
        return
    try:
        line = setup.uart.readline() # Read data until "\n" or timeout
        if line:
            line = line.decode("utf-8") # Convert from bytes to string
            line = line.strip("\n") # Strip end line
            return "".join(line).split(",")
    except Exception as error:
        print(error)

def run():
    global clock, on_off_state, snd_on, on_off_state, tuning_locked
    global motor_angle, radio_band_total, radio_band_list

    radio_band_list = get_radio_bands(settings.stations_root_folder)
    radio_band_total = len(radio_band_list) - 1

    pygame.mixer.Channel(2).play(snd_on)
    pygame.mixer.Channel(2).set_volume(settings.effects_volume)

    print("****** Radiation King Radio is now running ******")
    resume_from_standby()

    while True:
        for event in pygame.event.get():
            handle_event(event)
        try:
            uart_message = receive_uart()
            if uart_message and len(uart_message) > 1:
                if uart_message[0] == "I":  # Information
                    print("UART Info:", uart_message[0], uart_message[1])

                #Button Input
                if uart_message[0] == "B" and on_off_state:
                    if uart_message[1] == "1":  # Button released
                        process_button_press(uart_message)
                    if uart_message[1] == "2":  # Button held
                        process_button_hold(uart_message)

                #ADC Input
                if uart_message[0] == "A" and on_off_state:
                    if uart_message[1] == "0":  # ADC_0
                        adc_0_value = float(uart_message[2])
                        set_volume_level(round(map_range(adc_0_value,settings.ADC_Min, settings.ADC_Max,settings.volume_min, 1), 3))
                        #print("UART: ADC_0 Value:", uart_message[2])

                    if uart_message[1] == "1": #ADC 1
                        motor_angle = float(uart_message[2])
                        #print("UART: ADC_1 Value:", float(uart_message[2]))

                # Power State
                if uart_message[0] == "P":
                    if uart_message[1] == "1":
                        print("UART Info: RP2040 called resume")
                        resume_from_standby()
                    if uart_message[1] == "0":
                        print("UART Info: RP2040 called Standby")
                        standby()
        except Exception as error:
               print("UART Error:", str(error))
        if on_off_state:
            if setup.gpio_available:
                check_gpio_input()
            tuning()
        clock.tick(200)

def process_button_press(uart_message):
    print("UART: Held button", uart_message[2])
    if uart_message[2] == "0" and active_station: active_station.rewind()
    if uart_message[2] == "1": prev_band()
    if uart_message[2] == "2" and active_station:
        active_station.play_pause()
    if uart_message[2] == "3": next_band()
    if uart_message[2] == "4" and active_station: active_station.fast_forward()

def process_button_hold(uart_message):
    print("UART: Released button", uart_message[2])
    if uart_message[2] == "0" and active_station: active_station.prev_song()
    if uart_message[2] == "1": prev_station()
    if uart_message[2] == "2" and active_station:
        active_station.randomize_station()
        active_station.next_song()
    if uart_message[2] == "3": next_station()
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
        self.start_time = master_start_time
        self.sum_of_song_lengths = 0
        self.start_pos = 0
        self.last_play_position = 0
        self.last_playtime = 0
        pygame.mixer.music.set_endevent(settings.EVENTS['SONG_END'])


    def live_playback(self):
        global volume
        self.start_pos = 0
        if self.files:
            self.start_pos = max(time.time() - self.start_time, 0)
            # print("Time based start_pos =", round(self.start_pos, 3))

            #  Subtract time until we are below the station length
            if self.station_length and self.start_pos > self.station_length:
                print("Info: start_pos longer than station length", round(self.start_pos, 3), self.station_length)
                while self.start_pos > self.station_length:
                    print("Info: Looping station list")
                    self.start_pos = self.start_pos - self.station_length

            #  Find where in the station list we should be base on start position
            self.song_length = self.song_lengths[0]  # length of the current song
            if self.song_length and self.start_pos > self.song_length:
                print("Info: Start_pos longer than song length, skipping songs", round(self.start_pos, 3), self.song_length)

                while self.start_pos > self.song_length:
                    # print("Skipping song", self.song_length)
                    self.files.rotate(-1)
                    self.song_lengths.rotate(-1)
                    self.start_pos = self.start_pos - self.song_length
                    self.song_length = self.song_lengths[0]
                self.start_time = time.time() - self.start_pos

            self.filename = self.files[0]
            song = self.filename

            print("Info: Playing =", self.filename,
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
        self.start_time = time.time()
        self.start_pos = 0
        self.filename = self.files[0]
        song = self.filename

        print("Info: Playing next song =", self.filename,
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


    def prev_song(self):
        self.files.rotate(1)
        self.song_lengths.rotate(1)
        self.start_time = time.time()
        self.start_pos = 0
        self.live_playback()
        print("Action: Prev song")


    def randomize_station(self):
        seed = time.time()
        random.Random(seed).shuffle(self.files)
        random.Random(seed).shuffle(self.song_lengths)
        print("Info: Randomized song order")


    def fast_forward(self):
        global master_start_time
        self.start_time = self.start_time - settings.fast_forward_increment
        if self.start_time < master_start_time:
            master_start_time = self.start_time
        print("Action: Fast forward", settings.fast_forward_increment, self.start_time, master_start_time)
        self.live_playback()


    def rewind(self):
        global master_start_time
        self.start_time = max(self.start_time + settings.rewind_increment, master_start_time)
        print("Action: Rewind", settings.fast_forward_increment, self.start_time, master_start_time)
        self.live_playback()

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
    global volume, radio_band, station_num
    saved_ini = configparser.ConfigParser()
    try:
        assert os.path.exists(settings.save_file)
        saved_ini.read(settings.save_file)
    except Exception as error:
        print("Warning: Error reading the following:", str(error))
    saved_ini["audio"] = {"volume": str(volume), "station": str(station_num), "band": str(radio_band)}
    with open(settings.save_file, 'w') as configfile:
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
    print("Action: Exiting")

if __name__ == "__main__":
    run()
