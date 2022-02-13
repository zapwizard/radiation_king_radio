import os
import sys
import settings
import serial
#import distutils
import shutil
import filecmp
import mount
import time

def mergeFlatDir(src_dir, dst_dir):
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    for item in os.listdir(src_dir):
        copyFile(os.path.join(src_dir, item), os.path.join(dst_dir, item))

def copyFile (sfile, dfile):
    if os.path.isfile(sfile):
        shutil.copy2(sfile, dfile)

def isAFlatDir(sDir):
    return not any(
        os.path.isdir(os.path.join(sDir, item)) for item in os.listdir(sDir)
    )


def copyTree(src, dst):
    filecmp.clear_cache()
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isfile(s):
            if not os.path.exists(dst):
                os.makedirs(dst)
            if (
                not filecmp.cmp(s, d, shallow=False)
                and os.stat(s).st_mtime - os.stat(d).st_mtime > 1
            ):
                copyFile(s, d)
                print("Startup: Copied file to:", d)

        if os.path.isdir(s):
            is_recursive = not isAFlatDir(s)
            if is_recursive:
                copyTree(s, d)
            else:
                mergeFlatDir(s, d)


os.environ["JOBLIB_TEMP_FOLDER"] = "/tmp"

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
            print("Initializing pin %s as action '%s'" % (pin, settings.GPIO_ACTIONS[pin]))
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            gpio_actions[pin] = settings.GPIO_ACTIONS[pin]
        GPIO.setup(17, GPIO.IN)  # On off shim
        if not GPIO.input(17):
            print("GPIO17 Held low at startup, exiting")
            sys.exit()
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
                if vendor == settings.PICO_VENDOR and model == settings.PICO_MODEL and size == settings.PICO_SIZE :
                    device_name = mount.get_device_name(device)
                    print("USB Search: Mounting",device)
                    mount.mount(device, name=settings.PICO_FOLDER_NAME)  # mount the device
                    usb_path = mount.get_media_path(settings.PICO_FOLDER_NAME)
                    if os.path.isdir(usb_path):
                        print("USB Search: Found a Pi Pico at: Path:", usb_path, "Vendor:", vendor, "Model:", model,
                              "Size:", size, )
                    else:
                        print("USB Search: Error: Pi Pico not mounted")
                        sys.exit()
                else:
                    print("USB search: Found","usb_path=",usb_path,"Vendor=",vendor,"Size=",size,"Model=",model)
    except Exception as error:
        print("Error: USB Search: Error finding Pi Pico")
        sys.exit(error)

    if usb_path:
        #Copy Pi Pico Source Code to Pi Pico:
        try: #copy all files in Pi Pico folder over to the Pi
            print("Startup: Copying any new files to Pi Pico")
            #distutils.dir_util._path_created.clear()
            #time.sleep(0.5)
            #distutils.dir_util.copy_tree(settings.PICO_SOURCE, usb_path, preserve_symlinks=1, update=1, verbose=1)
            copyTree(settings.PICO_SOURCE, usb_path)
            time.sleep(5) # Give the pico a chance to boot up
        except Exception as error:
            print("Error copying files to Pi Pico:")
            sys.exit(error)
    else:
        sys.exit("Error: USB Search: No path to Pi Pico files")

    # Board to Board UART:
    uart = None
    while not uart:
        uart = None
        print("Startup: Trying to open serial port:", settings.SERIAL_PORT)
        try:
            uart = serial.Serial(settings.SERIAL_PORT, settings.BAUD_RATE, timeout=settings.UART_TIMEOUT)
        except:
            time.sleep(5)
    try:
        uart.write(b'I,Serial Start\n')  # write a string
        print("Startup: Opened UART port:", uart.name)  # check which port was really used
    except Exception as e:
        print("Error: Could not open a serial connection to the Pi Pico")
        _, err, _ = sys.exc_info()
        print("Uart Error: (%s)" % err, e)
        uart = False
        sys.exit()
else:
    print("Not running on a Raspberry Pi")