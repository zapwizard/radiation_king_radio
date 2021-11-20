# radiation_king_radio
A pygame based radio player with some unique radio band and live playback features.

This was designed to run on a Raspberry Pi along with other off the shelf boards, but could be adapted to other hardware.

This is still at work in progress.
See the project log at the link below:
https://www.therpf.com/forums/threads/zaps-fallout-radiation-king-radio.304867/

# Features
-Simulated live radio station playback
-Multiple virtual radio bands
-Authentic fuzz and tuning sounds
-Automatic parsing of folders and audio files
-Automatic distribution of the radio stations across an analog dial
-Cached metadata for faster handling of large libraries
-Stereo playback
-Analog Air Core Motor control
-Potentiometer and Rotary encoder inputs
-Manual button activated tuning
-Manual song skipping
-Playback ordered or randomized stations
-Standby mode

# Coming soon
-Ultrasonic Remote control

# Audio Folders
The audio folders first have a "radio band" folder. Think of this like AM, FM, Shortwave, etc...
These are single folders that contain sub-folders with audio files inside. Name the folders with 00, 01, 02, etc... at the front in order to set the order of the radio bands. Empy example folders have been included.

Inside each radio band folder you will place sub-folders with audio files inside. Each of these become a "Radio Station"
See the "ZZ_test_stations" folder for an example.
The program will only look for .OGG audio files. So you will need to convert any MP3s to OGG before using them. The OGG format was selected to make the metadata processing optomized, as well as take up less CPU. I have fourn fre:ac to be a good fast convertor.

Naming the radio stations with 00, 01 , 02 etc.. will set their order on the dial. Similar naming for songs is required for ordered file playback.

# Station.ini
Each radio station folder should have a file "Station.ini". (But isn't required)
This contains the radio station name, as well as whether the radio station should have ordered or random playback.
This file is required for the caching feature to work.

Example:
	[metadata]
	station_name = The Shadow
	ordered = True
	
#settings.py
This is a file that has settings you may want to tweak. Such as the volume of the static background sounds, or whether or not to build the cache file.
