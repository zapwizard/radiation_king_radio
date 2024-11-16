import os
import sys
import settings
import serial
import distutils
import shutil
import filecmp
import mount
import time
import signal

# Add a flag to indicate whether the script should exit
exit_requested = False

def signal_handler(sig, frame):
    """Handle CTRL + C signal to exit gracefully."""
    global exit_requested
    print("CTRL + C pressed. Exiting gracefully...")
    exit_requested = True

# Register signal handler for SIGINT
signal.signal(signal.SIGINT, signal_handler)

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
                print("INFO: Copied the file:", d)

        if os.path.isdir(s):
            is_recursive = not isAFlatDir(s)
            if is_recursive:
                copyTree(s, d)
            else:
                mergeFlatDir(s, d)

os.environ["JOBLIB_TEMP_FOLDER"] = "/tmp"

print("INFO: Starting up")

if os.geteuid() != 0:
    sys.exit('ERROR: This script must be run as root!')

# Detect if running on a Raspberry Pi
PI = os.name == "posix"

gpio_actions = {}

usb_path = None # path to Pi Pico Files

if PI:
    import board

    try:
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)  # Using GPIO numbering
        gpio_available = True
        #for pin in settings.GPIO_ACTIONS.keys():
        #    print("INFO: Initializing pin %s as action '%s'" % (pin, settings.GPIO_ACTIONS[pin]))
        #    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        #    gpio_actions[pin] = settings.GPIO_ACTIONS[pin]
        #GPIO.setup(17, GPIO.IN)  # On off shim
        #if not GPIO.input(17):
        #    print("GPIO17 Held low at startup, exiting")
        #    sys.exit()
    except Exception as e:
        _, err, _ = sys.exc_info()
        print("WARNING: GPIO UNAVAILABLE (%s)" % err, e)
        gpio_available = False


    # detect if the Pi Pico is on the USB bus.
    try:
        usb_devices = (mount.list_media_devices())
        if not usb_devices:
            print("USB: Error cannot find any removable USB devices:", usb_devices, "Exiting")
            sys.exit()

        else:
            for device in usb_devices:
                vendor = mount.get_vendor(device)
                size = mount.get_size(device)
                model = mount.get_model(device)
                partition = mount.get_partition(device)
                if vendor == settings.PICO_VENDOR and model == settings.PICO_MODEL and size == settings.PICO_SIZE :
                    print("USB: Found a:", vendor, ", Model:,", model, ", Size:", size, ", Partition:", partition)
                    usb_path = mount.get_media_path(settings.PICO_FOLDER_NAME)
                    #mount.unmount(device) # Attempt to unmount existing device
                    #mount.mount(device, name=settings.PICO_FOLDER_NAME)  # mount the device

                    if mount.is_mounted(partition):
                        usb_path = "/media/" + settings.PICO_FOLDER_NAME
                        if os.path.isdir(usb_path):
                            print("USB:", partition ,"at path:", usb_path)
                        else:
                            print("USB: Error: Could not find path for", usb_path, "Exiting")
                            sys.exit()
                    else:
                        # Try to remove and unmount pico
                        try:
                            os.system("sudo umount -l " + partition)
                        except Exception as error:
                            print("USB: Error: Could not unmount:", partition, "Exiting")
                            sys.exit(error)
                        try:
                            os.system("sudo rm -r -f " + usb_path)
                        except Exception as error:
                            print("USB: Error: Could not remove folder:", usb_path, "Exiting")
                            sys.exit(error)

                        # Try to mount the pico
                        try:
                            os.system("sudo mkdir -p " + usb_path)
                        except Exception as error:
                            print("USB: Error: Could not make folder:", usb_path,"Exiting")
                            sys.exit(error)
                        try:
                            os.system("sudo mount %s %s" % (partition, usb_path))
                        except Exception as error:
                            print("USB: Error: Could not mount:", partition,"Exiting")
                            sys.exit(error)
                else:
                    print("USB: Error: USB: Error finding Pi Pico, Exiting")
                    sys.exit()

    except Exception as error:
        print("USB: Error: USB: Error finding any USB devices, Exiting")
        sys.exit(error)

    #Copy Pi Pico Source Code to Pi Pico:
    if usb_path:
        try:
            print("INFO: Checking for new Pi Pico files")
            copyTree(settings.PICO_SOURCE, usb_path)
            time.sleep(5)  # Give the pico a chance to boot up
        except Exception as error:
            print("ERROR: Could not copy files Pi Pico:")
            try:
                print(error)
                print("WARNING: Trying alternate copy method")
                distutils.dir_util._path_created.clear()
                time.sleep(0.5)
                distutils.dir_util.copy_tree(settings.PICO_SOURCE, usb_path, preserve_symlinks=1, update=1, verbose=1)
            except Exception as error:
                print("ERROR: Could not copy files Pi Pico:")
                sys.exit(error)
    else:
        print("ERROR: No USB Path found, Exiting")
        sys.exit()

    # Board to Board UART initialization
    uart = None
    print("INFO: Trying to open serial port:", settings.SERIAL_PORT, "(This can take several seconds)")

    # Retry opening the serial port until successful or until exit is requested
    while not uart and not exit_requested:
        try:
            uart = serial.Serial(settings.SERIAL_PORT, settings.BAUD_RATE, timeout=settings.UART_TIMEOUT)
            print("Startup: Opened UART port:", uart.name)  # Check which port was really used
        except serial.SerialException as e:
            print("Error: Could not open a serial connection to the Pi Pico")
            print("ERROR: Uart:", e)
            uart = None  # Reset to None to continue the loop
            time.sleep(3)  # Wait before retrying
        except KeyboardInterrupt:
            # If CTRL + C is pressed, handle it gracefully
            print("Interrupted by user. Exiting...")
            exit_requested = True
            
    # Cleanup and exit
    if exit_requested:
        # Perform any necessary cleanup here
        if uart and uart.is_open:
            uart.close()
        sys.exit(0)
else:
    print("Not running on a Raspberry Pi")
   