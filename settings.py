import pygame

SAVE_FILE = "saved.ini"

EVENTS = {
    'BLINK': pygame.USEREVENT + 1,
    'SONG_END': pygame.USEREVENT + 2,
    'PLAYPAUSE': pygame.USEREVENT + 3,
}

ACTIONS = {
    pygame.K_1: "button_1",
    pygame.K_2: "button_2",
    pygame.K_3: "button_3",
    pygame.K_4: "button_4",
    pygame.K_5: "button_5",
}

# GPIO.setmode(GPIO.BCM)  # Using GPIO numbering
#GPIO_ACTIONS = {
#    17: "power_off",  # GPIO 17
#}

DISABLE_HEARTBEAT_LED = False # Note you won't be able to determine if the code is running without using a terminal

# To speed up the boot process: Song and station data caching is used
# Anytime you change your music files, you must set the value of RESET_CACHE to True and then reboot
# Depending on the size of your music library caching can take a long time
# Once the cache is re-built the radio will operate as normal
# The RESET_CACHE settings should be set to False before your the next reboot
# You can optionally reset the cache on any single folder by deleting the [CACHE] section in the station.ini file.
RESET_CACHE = False

# Music related
STATIONS_ROOT_FOLDER = "radio/"
STATIC_SOUNDS_FOLDER = "sounds/Static_Chunks"  # Place multiple static noise files here to randomize the noise
STATIC_VOLUME = 0.1  # 0-1 float
STATIC_VOLUME_MIN = 0.008  # Minimum static level, used to ensure some static at low volumes (Over ridden if volume is zero)
VOLUME_STEP = 0.008 # 0.008 seems to be the lowest volume level possible
VOLUME_MIN = STATIC_VOLUME_MIN  # Use static_volume_min if you want the radio to never be completely silent
FAST_FORWARD_INCREMENT = 5  # in seconds
REWIND_INCREMENT = 5 # in seconds

# Tuning related:
TUNING_NEAR = 4 # Adjusts how near you need to be to hear a station in the static while turning
TUNING_LOCK_ON = 6  # Adjusts how precise you need to be to land on a station (Higher = more accuracy required, must be larger than tuning_near)
BAND_CHANGE_VOLUME = 0.5 # Float: How loud the band changing sound effect is played (Multiplier of current volume)
EFFECTS_VOLUME = 0.6 # How loud the on/off and other sound effects are played
TIME_ZONE = 'US/Central'

# Air Core Motor Related:
MOTOR_MIN_ANGLE = 14 # This must match the numbers in pico_settings.py
MOTOR_MAX_ANGLE = 168
MOTOR_RANGE = MOTOR_MAX_ANGLE - MOTOR_MIN_ANGLE
SWEEP_ENABLED = True

#Sound effects
SOUND_OFF = "sounds/UI_Pipboy_Radio_Off.ogg"
SOUND_ON = "sounds/UI_Pipboy_Radio_On.ogg"
SOUND_BAND_CHANGE = "sounds/Band_Change.ogg"

#Uart Related:
BAUD_RATE = 115200 #115200 is the default, 9600 will cause slow performance.
UART_TIMEOUT = 0.1
UART_HEARTBEAT_INTERVAL = 2
PICO_HEARTBEAT_TIMEOUT = 30 #Must be larger than the sending interval on Pi Pico
SERIAL_PORT = "/dev/ttyACM1" # use for USB serial data exchange
#serial_port = "/dev/serial0 " # use for UART pins

#LED related:
GAUGE_PIXEL_QUANTITY = 7 # Must be 1 less than pico_settings gauge_pixel_qty

#Pi Pico related:
# These are used to verify the pi pico is connected
PICO_VENDOR = "Raspberr"
PICO_MODEL = "Pico"
PICO_SIZE = 1049088
PICO_SOURCE = "pi_pico_files/" #folder with Pi Pico files
PICO_FOLDER_NAME = "pico" # /media/xxx Mount name on the Pi Zero
