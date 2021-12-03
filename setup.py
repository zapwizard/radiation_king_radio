import os
import sys
import time
import settings

print("Starting up")

if not os.geteuid() == 0:
    sys.exit('This script must be run as root!')

# Detect if running on a Raspberry Pi
PI = os.name == "posix"


gpio_actions = {}
neopixel = False
neopixels = None


if PI:
    import board

    # Air Core Motor related:
    import digitalio

    coils = (
        digitalio.DigitalInOut(board.D12),  # A1
        digitalio.DigitalInOut(board.D13),  # A2
        digitalio.DigitalInOut(board.D23),  # B1
        digitalio.DigitalInOut(board.D24),  # B2
    )
    for coil in coils:
        coil.direction = digitalio.Direction.OUTPUT

    # NeoPixel Related
    neopixel_pin = board.SPI()
    neopixel_number = 5
    neopixel_brightness = 0.1
    try:
        import neopixel_spi

        neopixel_order = neopixel_spi.GRBW  # For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
        neopixels = neopixel_spi.NeoPixel_SPI(neopixel_pin, neopixel_number,
                                              brightness=neopixel_brightness, auto_write=True,
                                              pixel_order=neopixel_order, bit0=0b10000000)  # Raspberry Pi wiring!
        neopixel = True
        neopixels.fill((0, 0, 0, round(settings.neo_pixel_default / 10)))
    except Exception as e:
        neopixel = False
        print("Error: NeoPixels not found", e)

    # Motor Driver Related
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
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("Error: Motor driver failed: (%s)" % err, e)

    try:
        import board
        import adafruit_pcf8591.pcf8591 as PCF
        from adafruit_pcf8591.analog_in import AnalogIn
        from adafruit_pcf8591.analog_out import AnalogOut

        i2c = board.I2C()
        pcf = PCF.PCF8591(i2c)

        ADC_0 = AnalogIn(pcf, PCF.A0)  # Use a switched linear potentiometer for the tuning control.
        ADC_1 = AnalogIn(pcf, PCF.A1)
        ADC_2 = AnalogIn(pcf, PCF.A2) # I recommend using a switched "Audio" or logarithmic potentiometer for the volume control
        ADC_3 = AnalogIn(pcf, PCF.A3)

        # DAC = AnalogOut(pcf, PCF.OUT)

        ADC = True
    except Exception as e:
        ADC = False
        print("Error: ADC not detected: (%s)" % err, e)

    try:
        import buttonshim
        buttonshim.set_pixel(0x16, 0x00, 0x00)
    except Exception as e:
        buttonshim = None
        print("Error: Button shim not detected: (%s)" % err, e)

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
            import _pixelbuf as pixel_buffer
        except ImportError:
            import adafruit_pypixelbuf as pixel_buffer

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
        print("Error: Rotary Encoder failed (%s)" % err, e)
        rotary = None


else:
    print("Not running on a Raspberry Pi")