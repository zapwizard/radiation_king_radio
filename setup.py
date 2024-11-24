import os
import sys
import shutil
import time
import serial
import distutils.dir_util
import errno
import signal
from mount import list_media_devices, get_vendor, get_model, get_size, get_partition, get_media_path, is_mounted
import serial.tools.list_ports
import settings

print("SETUP.PY Start")

# Global Variables
exit_requested = False
uart = None
usb_path = None
partition = None
gpio_available = None

# Signal Handler
def signal_handler(sig, frame):
    """Handle CTRL + C signal to exit gracefully."""
    global exit_requested
    print("CTRL + C pressed. Exiting gracefully...")
    exit_requested = True

# Register signal handler for SIGINT
signal.signal(signal.SIGINT, signal_handler)

# GPIO Initialization
def detect_and_initialize_gpio():
    """Detect and initialize GPIO pins for Raspberry Pi."""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)  # Using GPIO numbering
        print("INFO: GPIO successfully initialized.")
        return True
    except ImportError:
        print("WARNING: RPi.GPIO not installed or unavailable.")
    except Exception as e:
        print(f"WARNING: GPIO unavailable: {e}")
    return False

# Validate Serial Port
def validate_serial_port(port_name):
    """Validate if the specified serial port is available."""
    available_ports = [port.device for port in serial.tools.list_ports.comports()]
    if port_name not in available_ports:
        print(f"ERROR: Specified port {port_name} not found. Available ports: {available_ports}")
        return False
    print(f"INFO: Port {port_name} is available.")
    return True

# Reset Serial Port
def reset_serial_port(port_name):
    """Attempt to reset a locked or busy serial port."""
    try:
        os.system(f"fuser -k {port_name}")
        print(f"INFO: Reset serial port {port_name}.")
    except Exception as e:
        print(f"ERROR: Failed to reset port {port_name}: {e}")

# UART Connection
def open_serial_connection():
    """Open the UART connection to the Pi Pico."""
    global uart, exit_requested
    max_retries = 10
    retry_count = 0
    start_time = time.time()
    total_timeout = 60  # Timeout after 60 seconds

    while not uart and retry_count < max_retries and not exit_requested:
        if time.time() - start_time > total_timeout:
            print("ERROR: UART connection attempt timed out.")
            uart = None
            return  # Exit without crashing the system

        try:
            print(f"INFO: Attempting to connect to UART on port {settings.UART_SETTINGS['serial_port']} "
                  f"at {settings.UART_SETTINGS['baud_rate']} baud.")

            uart = serial.Serial(
                port=settings.UART_SETTINGS["serial_port"],
                baudrate=settings.UART_SETTINGS["baud_rate"],
                timeout=settings.UART_SETTINGS["timeout"],
                write_timeout=1.0
            )

            if uart.is_open:
                print(f"INFO: UART successfully connected on port {uart.name}")
                return  # Exit the loop on success
        except serial.SerialException as e:
            print(f"ERROR: Failed to connect to UART: {e}")
            uart = None
            retry_count += 1
            time.sleep(3)  # Retry after delay
        except Exception as e:
            print(f"ERROR: Unexpected UART error: {e}")
            uart = None
            retry_count += 1
            time.sleep(3)

    print("ERROR: UART connection failed after maximum retries.")
    uart = None


# Pi Pico Detection and Mounting
def detect_and_mount_pico():
    """Detect and mount the Pi Pico device."""
    global usb_path, partition
    try:
        # List all media devices
        usb_devices = list_media_devices()
        print(f"DEBUG: Detected USB devices: {usb_devices}")
        if not usb_devices:
            print("ERROR: No removable USB devices detected.")
            sys.exit(1)

        # Iterate over detected devices
        for device in usb_devices:
            try:
                vendor = get_vendor(device) or "UNKNOWN_VENDOR"
                model = get_model(device) or "UNKNOWN_MODEL"
                size = get_size(device) or "UNKNOWN_SIZE"
                partition = get_partition(device) or "UNKNOWN_PARTITION"

                print(f"DEBUG: Found device - Vendor: {vendor}, Model: {model}, Size: {size}, Partition: {partition}")

                # Check if the device matches Pi Pico specifications
                if (
                    vendor.lower() == settings.PICO["vendor"].lower()
                    and model.lower() == settings.PICO["model"].lower()
                    and int(size) == settings.PICO["size"]
                ):
                    print("INFO: Pi Pico detected.")
                    usb_path = get_media_path(settings.PICO_FOLDER_NAME)
                    print(f"DEBUG: Media path resolved to: {usb_path}")

                    # Check if already mounted
                    if not is_mounted(partition):
                        print(f"INFO: Device not mounted. Attempting to mount {partition}...")
                        remount_pico(partition, usb_path)

                    # Validate the mount path
                    if os.path.isdir(usb_path):
                        print(f"INFO: Pi Pico successfully mounted at {usb_path}")
                        return usb_path
                    else:
                        print(f"ERROR: Mount path {usb_path} does not exist or is inaccessible.")
                        sys.exit(1)
                else:
                    print(f"WARNING: Device mismatch - Vendor: {vendor}, Model: {model}, Size: {size}")
            except Exception as e:
                print(f"ERROR: Failed to retrieve device information for {device}: {e}")
        
        # If no valid Pico device is found
        print("ERROR: Pi Pico not detected. Please verify the connected devices.")
        sys.exit(1)

    except Exception as e:
        print(f"ERROR: Unable to detect USB devices: {e}")
        sys.exit(1)


def remount_pico(partition, mount_path):
    """Unmount and remount the Pi Pico."""
    try:
        print(f"INFO: Attempting to remount {partition} at {mount_path}...")

        # Check if already mounted and unmount if necessary
        if is_mounted(partition):
            print(f"INFO: {partition} is currently mounted. Unmounting...")
            os.system(f"sudo umount -l {partition}")

        # Clean up the mount path
        if os.path.isdir(mount_path):
            try:
                print(f"INFO: Cleaning up mount path {mount_path} (if empty)...")
                os.rmdir(mount_path)  # Only removes if empty
            except OSError as e:
                if e.errno != errno.ENOTEMPTY:
                    raise

        # Recreate the mount path
        os.makedirs(mount_path, exist_ok=True)
        print(f"INFO: Mounting {partition} at {mount_path}...")
        
        # Attempt to mount the partition
        mount_cmd = os.system(f"sudo mount {partition} {mount_path}")
        if mount_cmd != 0:
            raise OSError(f"Mount command failed for {partition}.")

        print(f"INFO: Successfully mounted {partition} at {mount_path}")
    except Exception as e:
        print(f"ERROR: Failed to remount Pi Pico: {e}")


# Copy Updated Files
def copy_updated_files(src, dst):
    """
    Copy only new or modified files from src to dst.
    """
    try:
        for root, _, files in os.walk(src):
            for file_name in files:
                src_file = os.path.join(root, file_name)
                rel_path = os.path.relpath(root, src)
                dst_file = os.path.join(dst, rel_path, file_name)

                # Ensure the destination directory exists
                dst_dir = os.path.dirname(dst_file)
                if not os.path.exists(dst_dir):
                    print(f"DEBUG: Creating directory {dst_dir}")
                    os.makedirs(dst_dir)

                # Check file size and modification time
                src_mtime = os.path.getmtime(src_file)
                dst_mtime = os.path.getmtime(dst_file) if os.path.exists(dst_file) else 0
                src_size = os.path.getsize(src_file)
                dst_size = os.path.getsize(dst_file) if os.path.exists(dst_file) else -1

                #print(f"DEBUG: Checking file: {src_file}")
                #print(f"DEBUG: Source mtime: {src_mtime}, Destination mtime: {dst_mtime}")
                #print(f"DEBUG: Source size: {src_size}, Destination size: {dst_size}")

                # FAT timestamp rounding fix and file size check
                if (
                    abs(src_mtime - dst_mtime) > 2 or  # Allow for up to 2 seconds difference
                    src_size != dst_size               # Ensure file sizes match
                ):
                    print(f"INFO: Copying {src_file} to {dst_file}")
                    shutil.copy2(src_file, dst_file)
                #else:
                    #print(f"DEBUG: File is up to date: {src_file}")
    except Exception as e:
        print(f"ERROR: Failed to copy files from {src} to {dst}: {e}")




# Main File Copy Operation
def copy_files_to_pico():
    """Copy necessary files to the Pi Pico."""
    try:
        print(f"DEBUG: Copying files from {settings.PICO_SOURCE} to {usb_path}...")
        copy_updated_files(settings.PICO_SOURCE, usb_path)
        print("INFO: File copy process completed.")
    except Exception as e:
        print(f"ERROR: Copy operation failed: {e}")

def get_uart():
    global uart
    return uart

# Main Initialization
def initialize():
    global usb_path, partition
    gpio_available = detect_and_initialize_gpio()
    usb_path = detect_and_mount_pico()
    copy_files_to_pico()
    open_serial_connection()


# Main Execution
if __name__ == "__main__":
    initialize()
    print("INFO: Exiting gracefully.")
