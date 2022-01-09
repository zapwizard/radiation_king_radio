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
reset_cache = False  # Set this to force remaking the song cache files. Required if you changed any of the song files
stations_root_folder = "radio/"
static_sound_folder = "sounds/Static_Chunks"  # Place multiple static noise files here to randomize the noise
static_volume = 8  # Divisor: Larger number means lower volume
static_volume_min = 0.008  # Minimum static level, used to ensure some static at low volumes (Over ridden if volume is zero)
volume_step = 0.008 # 0.008 seems to be the lowest volume level possible
volume_min = 0.008  # Use 0.008 if you want the radio to never be silent
fast_forward_increment = 5  # in seconds
rewind_increment = 5 # in seconds

# Tuning related:
tuning_near = 3 # Adjusts how near you need to be to hear a station in the static while turning (3 = 1/3rd the gap between stations)
tuning_lock_on = 7  # Adjusts how precise you need to be to land on a station (must be larger than tuning_near)
band_change_volume = 1 # How loud the band changing sound effect is played (Divisor of current volume)
effects_volume = 0.8 # How loud the on/off and other sound effects are played

# Air Core Motor Related:
max_pwm_resolution = 255
motor_vcc = 5
motor_sin = 1  # Try flipping these four if your meter is running backwards
motor_cos = 0
forward = 0
backward = 1
motor_min_angle = 0  # Set this to zero and adjust the needle position first.
motor_max_angle = 150
motor_steps = motor_max_angle - motor_min_angle
motor_mid_point = round((motor_max_angle - motor_min_angle)/2)

#Sound effects
sound_off = "sounds/UI_Pipboy_Radio_Off.ogg"
sound_on = "sounds/UI_Pipboy_Radio_On.ogg"
sound_band_change = "sounds/Band_Change.ogg"

#Uart Related:
buad_rate = 19200
uart_timeout = 0.002

#ADC Related:
ADC_Min = 13
ADC_Max = 4096

#LED related:
led_qty = 7 # Subtract one due to zero address