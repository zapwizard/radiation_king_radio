# This file must be loaded onto the Pi Pico, and the Pico Rebooted at least once before taking affect.
# A full power off both the Pico and Zero may be required before the second serial port shows up on the Zero.
import usb_cdc
usb_cdc.enable(console=True, data=True)
