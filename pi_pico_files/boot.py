# This file must be loaded onto the Pi Pico, and the Pico power cycled at least once before taking affect.
# A full power off both the Pico and Zero is then required before the second serial port shows up on the Zero.
try:
    import usb_cdc
    usb_cdc.enable(console=True, data=True)
except Exception as error:
    print("usb_cdc Error:", error)