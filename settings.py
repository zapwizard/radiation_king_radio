import pygame

save_file = "saved.ini"

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
GPIO_ACTIONS = {
    17: "power_off",  # GPIO 17 (Shared with on/off shim)
}

# Music related
reset_cache = False  # Set this to force remaking the song cache files. Required if you changed any of the song files, otherwise keep false.
stations_root_folder = "radio/"
static_sound_folder = "sounds/Static_Chunks"  # Place multiple static noise files here to randomize the noise
static_volume = 0.1  # 0-1
static_volume_min = 0.008  # Minimum static level, used to ensure some static at low volumes (Over ridden if volume is zero)
volume_step = 0.008 # 0.008 seems to be the lowest volume level possible
volume_min = static_volume_min  # Use static_volume_min if you want the radio to never be completely silent
fast_forward_increment = 5  # in seconds
rewind_increment = 5 # in seconds



# Tuning related:
tuning_near = 0.3 # 0 - 1Adjusts how near you need to be to hear a station in the static while turning
tuning_lock_on = 8  # Adjusts how precise you need to be to land on a station (must be larger than tuning_near)
band_change_volume = 1 # How loud the band changing sound effect is played (Divisor of current volume)
effects_volume = 0.8 # How loud the on/off and other sound effects are played

# Air Core Motor Related:
motor_min_angle = 14 # This must match the settings on the Pico
motor_max_angle = 168
motor_range = motor_max_angle - motor_min_angle

#Sound effects
sound_off = "sounds/UI_Pipboy_Radio_Off.ogg"
sound_on = "sounds/UI_Pipboy_Radio_On.ogg"
sound_band_change = "sounds/Band_Change.ogg"

#Uart Related:
buad_rate = 115200
uart_timeout = 0.01
heartbeat_interval = 3
pico_heartbeat_timeout = 15 #Must be larger than the sending interval on Pi Pico
serial_port = "/dev/ttyACM1" # use for USB serial data exchange
#serial_port = "/dev/serial0 " # use for UART pins

#LED related:
gauge_pixel_qty = 7 # Must be 1 less than pico_settings gauge_pixel_qty

#Pi Pico related:
# These are used to verify the pi pico is connected
pico_vendor = "Raspberr"
pico_model = "Pico"
pico_size = 1049088
pico_source = "pi_pico_files/" #folder with Pi Pico files
pico_folder_name = "pico" # /media/xxx Mount name on the Pi Zero