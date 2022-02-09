
# Code prototype for ultrasonic PDM microphone
# Waiting for a Circuitpython patch before development can continue

import sys
import board
import audiobusio
import array
import time
import math
from ulab import numpy as np
import digitalio
import pico_settings as settings
#from ulab.scipy.signal import spectrogram

button_sample_time = 0
pdm_select = digitalio.DigitalInOut(board.GP2)
pdm_select.direction = digitalio.Direction.OUTPUT
pdm_select.value = False #Enable ultrasonic mode


mic = audiobusio.PDMIn(board.GP3, board.GP4, sample_rate=settings.REMOTE_SAMPLE_FREQUENCY, bit_depth=8, mono=True)
print ("SAMPLE_SIZE=",settings.REMOTE_SAMPLE_SIZE,"SAMPLE_FREQUENCY=",settings.REMOTE_SAMPLE_FREQUENCY,"returned mic.sample_rate=",mic.sample_rate)
samples = array.array('B', [1] * settings.REMOTE_SAMPLE_SIZE)

def benchmark_capture():
    start_capture_time = time.monotonic_ns()
    mic.record(samples, len(samples))
    sample_duration_ns = time.monotonic_ns() - start_capture_time
    ns_per_sample = sample_duration_ns / settings.REMOTE_SAMPLE_SIZE
    if ns_per_sample:
        max_sample_freq = round((1 / ns_per_sample) * 10**9)
        print(settings.REMOTE_SAMPLE_SIZE, "samples took",sample_duration_ns,"ns or", ns_per_sample, "ns per sample", "| Max Sample Frequency =", max_sample_freq)

# Remove DC bias before computing RMS.
def mean(values):
    return sum(values) / len(values)

def normalized_rms(values):
    minbuf = int(mean(values))
    samples_sum = sum(
        float(sample - minbuf) * (sample - minbuf)
        for sample in values
    )
    return math.sqrt(samples_sum / len(values))

def perform_fft(samples):
    real, imaginary = np.fft.fft(np.array(samples)) # Perform FFT
    return real[1:len(real)] # Remove DC offset

def determine_button(highest):
    if highest in settings.REMOTE_FREQS[0]:
        return 0
    elif highest in settings.REMOTE_FREQS[1]:
        return 1
    elif highest in settings.REMOTE_FREQS[2]:
        return 2
    elif highest in settings.REMOTE_FREQS[3]:
        return 3
    else:
        return 4

def determine_frequencies():
    hz_per_sample = settings.REMOTE_SAMPLE_FREQUENCY / settings.REMOTE_SAMPLE_SIZE
    mic.record(samples, len(samples))

    #Perform FFT on half the samples
    fft_results = perform_fft(samples[0:round(len(samples)/2)])

    #Determine if samples are above THRESHOLD
    lowest_energy = round(abs(np.min(fft_results)))

    # Get the frequency of the highest amplitude
    highest_address = np.argmax(fft_results)
    highest_frequency = round(highest_address * hz_per_sample)

    if (
        highest_frequency > settings.REMOTE_FREQ_MIN
        and lowest_energy > settings.REMOTE_THRESHOLD
    ):
        return highest_frequency

benchmark_capture()

#
#while True:
    #now = time.time()
    #highest_frequency = determine_frequencies()
    #if now - button_sample_time > settings.REMOTE_SAMPLE_RATE and highest_frequency:
        #button_sample_time = now
        #determine_button(highest_frequency)

