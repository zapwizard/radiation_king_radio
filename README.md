# Radiation King Radio:
A pygame based music  player with some unique radio band and live playback features.

This was designed to run on a Raspberry Pi along with other off the shelf boards, but could be adapted to other hardware.

This is still at work in progress. [See the project log](https://www.therpf.com/forums/threads/zaps-fallout-radiation-king-radio.304867/).

## Features:
- Simulated live radio station playback
- Multiple virtual radio frequency bands
- Noise, fuzz and other tuning sounds effects
- Automatic parsing of folders and audio files
- Automatic distribution of the radio stations across an analog dial
- Cached song metadata for faster handling of large libraries
- Stereo playback
- Analog Air Core Motor control
- Switched potentiometer based volume and tuning inputs
- Manual button activated tuning
- Manual song skipping
- Fast-forward, rewind and pause
- Playback ordered or randomized stations
- Standby mode
- Neopixel lights with warm start/shutdown effect
- Ultrasonic Remote Control


#Licence:
Licence: Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)


## Audio Folders:
### Audio Files:
The program will only look for .OGG audio files. The OGG format was selected to make the metadata processing optimized, as well as take up less CPU.

I recommend using [Foobar2000](https://www.foobar2000.org/) along with [oggenc2.exe](https://www.rarewares.org/ogg-oggenc.php) as you can also normalize the files at conversion time.
First scan your library to apply Replaygain tags. Then convert the files using Foobar2000's convert command to apply Replaygain offset to the files while also converting them to .OGG
I used the "apply gain without clipping" option.

### Band Folders:
The audio folders first have a "radio band" folder. Think of this like sort of like AM, FM, Shortwave, etc...
In actuality, it works out best to use the bands for things like "Fallout 4 stations", "Fallout Mod Stations", "Holiday Stations", etc...
Prefix the name of the folders with 00, 01, 02, etc... to set the order of the radio bands. Example folders have been included.

### Station Folders:
Inside each radio band folder you will place sub-folders with audio files inside. Each folder will become a "Radio Station"
See the "ZZ_test_stations" folder for an example. There must be at least two radio stations inside a radio band folder.

Prefixing the names of the radio station folders with 00, 01, 02, etc... will set the order on the dial. Similar prefix naming of song files is required for ordered file playback.

The software will automatically spread the stations evenly across the dial. The amount of stations that can practically fit will depend on how far your dial can turn.
For example the dial on my design can move 150 degrees. So if there are 10 radio stations they will end up about 15 degrees apart on the dial. 


## station.ini files:
Each radio station folder should have a file named "Station.ini". 
This contains the radio station name, as well as whether the radio station should have ordered or random playback.
If the file is missing it will be created upon cache generation. The below data is required if you require ordered playback.

Example:
	[metadata]
	station_name = The Shadow
	ordered = True

#Software setup:
## settings.py file:
This is a file that has settings you may want to tweak. Such as the volume of the static background sounds, and whether to re-build the cache files.
Each time you alter the audio files you should enable caching, reboot, wait for the cache process to complete, and then disable caching after boot is complete.
You can operate the radio with caching always enabled, but it will make the boot up take a very long time.

## Pi Pico files:
The pi_pico_files folder contains the code for the Pi Pico. You must have already loaded CircuitPython prior to connecting the Pi Pico to the Pi Zero over USB.
The Pi Zero code will automatically copy the files needed to the Pi Pico. 
The Pi Pico will send its serial output to the Pi Zero over USB UART. To see USB serial playback otherwise you need to disable the print() command in the code.py files.

## Requirements:
Make sure and install all the requirements listed in requirements.txt on your Pi Zero.

## Auto running the script:
- Run `sudo raspi-config` on the Pi Zero. Select “Boot Options” then “Desktop/CLI” then “Console Autologin”
- Ensure the files are in `\home\pi\radking`
- Run `sudo nano /etc/profile`
- Add to the file:
  - `cd /`
  - `cd /home/pi/radking`
  -  `sudo /usr/bin/python -u /home/pi/radking/main.py &`

# Operation:
## How the "Live" playback works:
Each radio station is basically a table with a list of the audio files, as well the duration of each music file. Using a deque list allows the list to be looped with the top item being moved automatically to the bottom of the list.

When the radio starts up it records the current time as "master_start_time". Each radio station uses this as reference when the station started up.
When you tune into a station some amount of time has passed since the master start time. The code checks the first song on the list.
If the song is shorter than the time that has past: It moves it to the bottom of the list and the length of that song is also removed from the past duration. This repeats until the current song at the top of the list is longer than the remaining time. The code then jumps into the song at the remaining time.

But using this method each station acts as if it is playing back live. You can tune off of a station and go back and have it resume at the correct time.
The deque list has the advantage that we don't have to keep track of a current song index, and we can easily randomize, skip/rewind or pause playback without losing the live playback effect.

## Motor angle feedback loop:
Each radio station is assigned an angle on the radio dial, a sort of address. When you move the tuning knob, the code moves the motor to a certain angle. Then it checks to see if there is a radio station near, or at that angle.

By doing this in a feedback loop you don't have to worry about the exact positions of any single station, and it automatically adjusts to frequency bands with different numbers of stations.

The code automatically determines how precise the angle needs to be to allow for a lock on zone around each station. If you are near a station it will play back the station at a lower volume, with noise at the same time. The volume of the station rises as you get near it, and plays in the clear once you hit the lock on zone.
There is also an area with just noise between each station.

If you cram too many stations into a single band, there may be no empty space between stations and precise tuning will become nearly impossible. 

#Hardware:
The radio uses a Pi Zero W and a Pi Pico together. The Pi Zero provides the fast music access and playback, and the Pi Pico handles all the analog and GPIO.
A USB and UART link are required between the Pi Zero and Pi Pico.

An Adafruit Speaker Bonnet, or any other i2s audio device can be used for the speakers. This is connected to the Pi Zero.

A TB6622 Dual-H Bridge motor controller is connected to the Pi Pico and handles the Air core motor.

##Air Core Motor:
After testing a stepper motor, I decided to go back to an air-core motor. A stepper motor has only a certain number of steps. I found the stepper movement to look robotic even using half steps.
An air core motor however is purely analog and can smoothly move to any angle needed. The movement is much closer to the look of an old school radio. Powering an air core motor is actually simple using a dual-h-bridge controller.

##Potentiometer control:
I opted to use Potentiometers instead of rotary encoders for a similar reason to the air core motor, they are just more analog feeling. You should use a switched logarithmic "Audio" pot for the volume control, and a linear pot for the tuning control.
If you use a linear pot for both, adding a 680ohm resistor to one the ground legs of a 10k linear pot can somewhat emulate a log pot. Use a switched pot for the tuning control also if you want to disable the knob for manual/digital turning.

##Neopixels:
An array of 8 Neopixels are used to light up the gauge display. As you change bands, one LED will light up briefly to indicate which band number you are on.

##Ultra Sonic Remote:
Using a SPH0641LU4H-1 Mems Microphone, and PWM audio a 1950's mechanical remote can be setup to operate the radio. A high pass filter is applied to the audio prevent the music from interfering with the remote control.
A spectrogram of the ultrasonic samples is returned. The index of the highest peak determines which button has been pressed.
