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
        uart = serial.Serial('/dev/serial0', settings.BAUD_RATE, timeout= settings.UART_TIMEOUT)
        print("Success: Opened UART port:",uart.name)  # check which port was really used
        uart.write(b'I,Serial Start\n')  # write a string
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("UART UNAVAILABLE (%s)" % err, e)
        uart = False


    # detect if the RP2040 (Pi Pico) is on the USB bus.
    try:
        import mount















        import pyudev
        print("Startup: Searching for Pi Pico")

        context = pyudev.Context()
        removable = [device for device in context.list_devices(subsystem='block', DEVTYPE='disk') if
                     device.attributes.asstring('removable') == "1"]
        if not removable:
            sys.exit("Error cannot find any removable USB devices:", removable)
        elif len(removable) == 1:
            partitions = [device.device_node for device in
                          context.list_devices(subsystem='block', DEVTYPE='partition', parent=removable[0])]
            path_to_rp2040 = (", ".join(partitions))
            print("Removable partition found at:",path_to_rp2040, os.path.ismount(path_to_rp2040))
        else:
            print("Error: More than one removable disk found")
            for device in removable:
                #print("Devices:",device)
                partitions = [device.device_node for device in
                              context.list_devices(subsystem='block', DEVTYPE='partition', parent=device)]
                print("All removable partitions: {}".format(", ".join(partitions)))
    except Exception as error:
        sys.exit("Error finding RP2040:",error)

    #Copy Pi Pico Source Code to Pi Pico:
    import shutil

    # path to source directory
    src_dir = 'pi_pico_files'

    # path to destination directory
    dest_dir = path_to_rp2040

    # getting all the files in the source directory
    files = os.listdir(src_dir)
    print (files)
    files = os.listdir(dest_dir)
    print(files)
    sys.exit()

    #shutil.copytree(src_dir, dest_dir)

else:
    print("Not running on a Raspberry Pi")




