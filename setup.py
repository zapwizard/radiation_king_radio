import os
import sys
import settings
import serial
import distutils
import time
import mount

print("Starting up")

if os.geteuid() != 0:
    sys.exit('This script must be run as root!')

# Detect if running on a Raspberry Pi
PI = os.name == "posix"

gpio_actions = {}

usb_path = None # path to Pi Pico Files
device_name = None

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
        #GPIO.setup(16, GPIO.OUT) # On-board LED
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("GPIO UNAVAILABLE (%s)" % err, e)
        gpio_available = False


    # detect if the Pi Pico is on the USB bus.
    try:
        usb_devices = (mount.list_media_devices())
        if not usb_devices:
            print("USB search: Error cannot find any removable USB devices:", usb_devices)
            sys.exit()

        else:
            for device in usb_devices:
                vendor = mount.get_vendor(device)
                size = mount.get_size(device)
                model = mount.get_model(device)
                if vendor == settings.pico_vendor and model == settings.pico_model and size == settings.pico_size :
                    device_name = mount.get_device_name(device)
                    print("USB Search: Mounting",device)
                    mount.mount(device, name=settings.pico_folder_name)  # mount the device
                    usb_path = mount.get_media_path(settings.pico_folder_name)
                    if os.path.isdir(usb_path):
                        print("USB Search: Found a Pi Pico at: Path:", usb_path, "Vendor:", vendor, "Model:", model,
                              "Size:", size, )
                    else:
                        print("USB Search: Error: Pi Pico not mounted")
                        sys.exit()
                else:
                    print("USB search: Found","usb_path=",usb_path,"Vendor=",vendor,"Size=",size,"Model=",model)
    except Exception as error:
        print("USB Search: Error finding Pi Pico")
        sys.exit(error)

    if usb_path:
        #Copy Pi Pico Source Code to Pi Pico:
        try: #copy all files in Pi Pico folder over to the Pi
            print("Startup: Copying files to Pi Pico")
            distutils.dir_util._path_created.clear()
            distutils.dir_util.copy_tree(settings.pico_source, usb_path, preserve_symlinks=1, update=1, verbose=1)
        except Exception as error:
            print("Error copying files to Pi Pico:")
            sys.exit(error)
    else:
        sys.exit("USB Search: No path to Pi Pico files")

    # Board to Board UART:
    try:
        # Use a timeout of zero so we don't delay while waiting for a message.

        uart = serial.Serial(settings.serial_port, settings.buad_rate, timeout=settings.uart_timeout)
        print("Startup: Opened UART port:", uart.name)  # check which port was really used
        uart.write(b'I,Serial Start\n')  # write a string
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("Uart Error: (%s)" % err, e)
        uart = False

else:
    print("Not running on a Raspberry Pi")