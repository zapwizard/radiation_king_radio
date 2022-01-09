import os
import sys
import time
import settings
import serial

print("Starting up")

if os.geteuid() != 0:
    sys.exit('This script must be run as root!')

# Detect if running on a Raspberry Pi
PI = os.name == "posix"

gpio_actions = {}

if PI:
    import board

    try:
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)  # Using GPIO numbering
        gpio_available = True
        for pin in settings.GPIO_ACTIONS.keys():
            print("Initialing pin %s as action '%s'" % (pin, settings.GPIO_ACTIONS[pin]))
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            gpio_actions[pin] = settings.GPIO_ACTIONS[pin]
        GPIO.setup(17, GPIO.IN)  # On off shim
        GPIO.setup(16, GPIO.OUT) # On-board LED
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("GPIO UNAVAILABLE (%s)" % err, e)
        gpio_available = False

    #Board to Board UART:
    try:
        # Use a timeout of zero so we don't delay while waiting for a message.
        uart = serial.Serial('/dev/serial0', settings.buad_rate, timeout= settings.uart_timeout)
        print("Success: Opened UART port:",uart.name)  # check which port was really used
        uart.write(b'I,Serial Start\n')  # write a string
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("UART UNAVAILABLE (%s)" % err, e)
        uart = False

else:
    print("Not running on a Raspberry Pi")