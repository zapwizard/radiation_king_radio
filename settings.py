import pygame

# File paths
SAVE_FILE = "saved.ini"
STATIONS_ROOT_FOLDER = "radio/"
STATIC_SOUNDS_FOLDER = "sounds/STATIC_SOUNDS_FOLDER"
STATIC_PRELOAD_NUM = 6 #Control the number of preloaded static files
PICO_SOURCE = "pi_pico_files/"
PICO_FOLDER_NAME = "pico"

# Audio settings
AUDIO_SETTINGS = {
    "frequency": 44100,
    "size": -16,
    "channels": 2,
    "buffer": 8192,
}
VOLUME_SETTINGS = {
    "default": 0.05,
    "step": 0.008,
    "min": 0.008,
    "static_volume": 0.06,
    "static_min": 0.008,
    "effects": 0.6,
    "band_change": 0.5,
    "callout_volume": 1,
}
SOUND_EFFECTS = {
    "off": "sounds/UI_Pipboy_Radio_Off.ogg",
    "on": "sounds/UI_Pipboy_Radio_On.ogg",
    "band_change": "sounds/Band_Change.ogg",
    "error": "sounds/UI_VATS_APLow_On_01.ogg",
}
BAND_CALLOUT_SETTINGS = {
    "enabled": True,
    "file": "callout.ogg",
    "wait_for_completion": True,
}

# To speed up the boot process: Song and station data caching is used
# The code will try to detect if the song files change, but if it fails to do so
# you must set the value of RESET_CACHE to True and then reboot
# Depending on the size of your music library caching can take a very long time
# Once the cache is re-built the radio will operate as normal
# The RESET_CACHE settings must be set to False before your the next reboot
# You can optionally reset the cache on any single folder by deleting the [CACHE] section inside the station.ini file.
RESET_CACHE = False

# Radio tuning
TUNING_SETTINGS = {
    "near": 8, # Angular distance at which static will start playing at the same time as the station
    "lock_on": 2, # Angular distance at which the station will play in the clear
    "end_zone": 14, # Dead zones to ensure that a station isn't at the very ends of the dial
    "sweep_enabled": False, #Enable a sweeping effect at band changes
}

# Motor settings
MOTOR_SETTINGS = {
    "min_angle": 14,  # Angle, start of the dial
    "max_angle": 168,  # Angle, end of the dial
}

# Dynamically calculate the range
MOTOR_SETTINGS["range"] = MOTOR_SETTINGS["max_angle"] - MOTOR_SETTINGS["min_angle"]

# GPIO and hardware
DISABLE_HEARTBEAT_LED = False
GAUGE_PIXEL_QUANTITY = 7  # 1 less than Pico gauge_pixel_qty

# UART settings
UART_SETTINGS = {
    "baud_rate": 115200,
    "timeout": 0.1,
    "heartbeat_interval": 2,
    "heartbeat_timeout": 30,
    "serial_port": "/dev/ttyACM1",
}

# Events
EVENTS = {
    "BLINK": pygame.USEREVENT + 1,
    "SONG_END": pygame.USEREVENT + 2,
    "PLAYPAUSE": pygame.USEREVENT + 3,
}

# Miscellaneous
TICK = 200 # Max rate of the code loop, loops per second
FAST_FORWARD_INCREMENT = 5  # seconds
REWIND_INCREMENT = 5  # seconds
TIME_ZONE = "US/Central"

# Pi Pico detection
PICO = {
    "vendor": "Raspberr",
    "model": "Pico",
    "size": 1049088,
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
