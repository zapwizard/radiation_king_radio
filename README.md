# Radiation King Radio:
A pygame based music  player with some unique radio band and live playback features.

This was designed to run on a Raspberry Pi along with other off the shelf boards, but could be adapted to other hardware.

This is still at work in progress.
See the project log at the link below:
https://www.therpf.com/forums/threads/zaps-fallout-radiation-king-radio.304867/

# Features:
-Simulated live radio station playback 
-Multiple virtual radio frequency bands
-Noise, fuzz and other tuning sounds effects
-Automatic parsing of folders and audio files
-Automatic distribution of the radio stations across an analog dial
-Cached song metadata for faster handling of large libraries
-Stereo playback
-Analog Air Core Motor control
-Switched potentiometer based volume and tuning inputs
-Manual button activated tuning
-Manual song skipping
-Fast-forward, rewind and pause
-Playback ordered or randomized stations
-Standby mode
-Neopixel lights with warm start/shutdown effect

# Coming soon:
-Ultrasonic Remote control

# Audio Folders:
The audio folders first have a "radio band" folder. Think of this like AM, FM, Shortwave, etc...
These are single folders that contain multiple sub-folders with audio files inside. Name the folders with 00, 01, 02, etc... at the front in order to set the order of the radio bands. Empy example folders have been included.


Inside each radio band folder you will place sub-folders with audio files inside. Each of these become a "Radio Station"
See the "ZZ_test_stations" folder for an example. There must be at least two radio stations inside a radio band folder.

The program will only look for .OGG audio files. So you will need to convert any MP3s to OGG before using them. The OGG format was selected to make the metadata processing optimized, as well as take up less CPU. I have found fre:ac to be a good fast convertor.

Naming the radio stations with 00, 01 , 02 etc.. will set their order on the dial. Similar naming for songs is required for ordered file playback.

The program will automatically spread the stations across the dial, but the amount of stations that can practically fit will depend on how far your dial can turn.
For example the dial on mine can move 150 degrees. If I have 10 radio stations they will end up about 10 degrees apart on the dial.

# Station.ini files:
Each radio station folder should have a file named "Station.ini". (But isn't required)
This contains the radio station name, as well as whether the radio station should have ordered or random playback. 
If the file is missing it will be created upon cache generation. The below data is required if you want ordered playback.

Example:
	[metadata]
	station_name = The Shadow
	ordered = True
	
#settings.py file:
This is a file that has settings you may want to tweak. Such as the volume of the static background sounds, or whether or not to re-build the cache files.
Each time you alter the audio files you should enable caching, reboot, and then disable caching after boot is complete.

# How the "Live" playback works:
Each radio station is made up of a table with a list of the audio files, as well the duration of each music file. Using a deque list allows the list to be looped with the top item being moved automatically to the bottom of the list.

When the radio starts up it records the current time as "master_start_time". Each radio station uses this as reference when the station started up.
When you tune into a station some amount of time has passed since the start time. The code checks the first song on the list. If it is shorter than the amount time that has past since the start: It moves it to the bottom of the list. The length of that song is also removed from the duration of time that has past. This repeats until the current song at the top of the list is longer than the remaining time. The code then jumps into the song at the remaining time.

But using this method, each station acts as if it is playing live. You can tune off of a station and go back and have it resume at the correct time.
The deque list has the advantage that we don't have to keep track of a song index, and we can easily randomize, skip/rewind or pause playback without losing the live playback effect.

#Motor angle feedback loop:
Each radio station is assigned an angle on the radio dial. The exact position depends on the maximum angle the needle can move.
When you move the tuning knob, the code move the motor to a certain angle. Then it checks to see if there is a radio station near, or at that angle.

By doing this in a feedback loop you don't have to worry about the exact positions of any station, and it automatically adjusts to frequency bands with different numbers of stations.

The code automatically determines how precise the angle needs to be to allow for a lock on zone around each station. If you are near a station it will play back the station at a lower volume, with noise at the same time. The volume of the station rises as you get near it, and plays in the clear once you hit the lock on zone.
There is also an area with just noise between each station.

#Air Core Motor:
After testing a stepper motor, I decided to go back to an air-core motor. A stepper motor has only a certain number of steps. I found the stepper movement to look robotic even using half steps.
An air core motor however is purely analog and can smoothly move to any angle needed. The movement is much closer to the look of an old school radio. Powering an air core motor is actually simple using a dual-h-bridge controller.

#Potentiometer control:
I opted to use Potentiometers instead of rotary encoders for a similar reason to the air core motor, they are just more analog feeling. You should use a switched logarithmic "Audio" pot for the volume control, and a linear pot for the tuning control.
If you use a linear pot for both, adding a 680ohm resistor to one the ground legs of a 10k linear pot can somewhat emulate a log pot. Use a switched pot for the tuning control also if you want to disable the knob for manual/digital turning.