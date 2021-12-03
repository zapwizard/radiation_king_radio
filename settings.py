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
    # 25: "button_1",  # GPIO 25
    # 8: "button_2",  # GPIO_8
    # 7: "button_3",  # GPIO_7
    # 1: "button_4",  # GPIO_1
    # 16: "button_5",  # GPIO_16
    17: "power_off",  # GPIO 17 (Shared with on/off shim)
    # 4: Reserved for On/Off shim
    # 17 Reserved for On/Off Shim
    # 2: "button_shim_1", # Reserved for button shim
    # 3: "button_shim_2", # Reserved for button shim
    # 18: "i2s_1", # Reserved for i2s audio
    # 19: "i2s_2", # Reserved for i2s audio
    # 21: "i2s_3", # Reserved for i2s audio
    # 23: "motor_1", # Reserved for motor driver
    # 24: "motor_2", # Reserved for motor driver
    # 12: "motor_3", # Reserved for motor driver
    # 13: "motor_4", # Reserved for motor driver
}

# Music related
reset_cache = False  # Set this to force remaking the song cache files. Required if you changed any of the song files
stations_root_folder = "radio/"
static_sound_folder = "sounds/Static_Chunks"  # Place multiple static noise files here to randomize the noise
static_volume = 4  # Divisor: Larger number means lower volume
static_volume_min = 0.008  # Minimum static level, used to ensure some static at low volumes (Over ridden if volume is zero)
volume_step = 0.008 # 0.008 seems to be the lowest volume level possible
volume_min = 0.008  # Use 0.008 if you want the radio to never be silent
fast_forward_increment = 5  # in seconds
rewind_increment = 5 # in seconds

# Tuning related:
tuning_near = 3 # Adjusts how near you need to be to hear a station in the static while turning (3 = 1/3rd the gap between stations)
tuning_lock_on = 6  # Adjusts how precise you need to be to land on a station (must be larger than tuning_near)
band_change_volume = 1 # How loud the band changing sound effect is played (Divisor of current volume)
effects_volume = 0.8 # How loud the on/off and other sound effects are played

# Button related
hold_time = 1

# Rotary encoder related
rotary_pin_a = 0
rotary_pin_b = 5
rotary_switch = 6
rotary_speed = 0.2

# ADC related:
ADC_Samples = 2  # More samples means more smoothing, but slower response.
ADC_Min = 0
ADC_Max = 255

# Air Core Motor Related:
max_pwm_resolution = 255
motor_vcc = 5
motor_sin = 0
motor_cos = 1
forward = 0
backward = 1
motor_min_angle = 0
motor_max_angle = 180
motor_steps = motor_max_angle - motor_min_angle
motor_mid_point = round((motor_max_angle - motor_min_angle)/2)

# Neo Pixel Related:
neo_pixel_default = 255  # Default brightness
neo_pixel_time_frame = 0.003

