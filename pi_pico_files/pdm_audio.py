# Code prototype for ultrasonic PDM microphone
# Waiting for a Circuitpython patch before development can continue

import sys
import board
import audiobusio
import array
import time
import math
from ulab import numpy as np
from ulab.scipy.signal import spectrogram
import digitalio
import pico_settings as settings
from adafruit_simplemath import map_range

pdm_select = digitalio.DigitalInOut(board.GP2)
pdm_select.direction = digitalio.Direction.OUTPUT
pdm_select.value = False  # Enable ultrasonic mode
remote_sample_time = 0
hz_per_sample = settings.REMOTE_SAMPLE_FREQUENCY / settings.REMOTE_SAMPLE_SIZE

mic = audiobusio.PDMIn(board.GP3, board.GP4, sample_rate=settings.REMOTE_SAMPLE_FREQUENCY, bit_depth=8, mono=True)
print("SAMPLE_SIZE=", settings.REMOTE_SAMPLE_SIZE, "SAMPLE_FREQUENCY=", settings.REMOTE_SAMPLE_FREQUENCY,
      "returned mic.sample_rate=", mic.sample_rate)
samples = array.array('B', [0] * settings.REMOTE_SAMPLE_SIZE)


def benchmark_capture():
    start_capture_time = time.monotonic_ns()
    mic.record(samples, len(samples))
    sample_duration_ns = time.monotonic_ns() - start_capture_time
    ns_per_sample = sample_duration_ns / settings.REMOTE_SAMPLE_SIZE
    if ns_per_sample:
        max_sample_freq = round((1 / ns_per_sample) * 10 ** 9)
        print(settings.REMOTE_SAMPLE_SIZE, "samples took", sample_duration_ns, "ns or", ns_per_sample, "ns per sample",
              "| Max Sample Frequency =", max_sample_freq)

benchmark_capture()

print("hz_per_sample:", hz_per_sample)  # Debug
remote_high_pass = round(map_range(settings.REMOTE_FREQ_MIN,0,settings.REMOTE_SAMPLE_FREQUENCY,0,settings.REMOTE_SAMPLE_SIZE))
print("remote_high_pass:",remote_high_pass)

# Pad filter
padded_filter = np.array([0] * settings.REMOTE_SAMPLE_SIZE)
padded_filter[0:settings.FILTER.size] = settings.FILTER
print("padded_filter.size:",padded_filter.size)

def perform_fft(data):
    real, imaginary = np.fft.fft(np.array(data))  # Perform FFT
    return real[1:len(real)]  # Remove DC offset


def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def determine_button(highest):
    if isclose(highest, settings.REMOTE_VALID[0], abs_tol=settings.REMOTE_TOLERANCE):
        return 0
    elif isclose(highest, settings.REMOTE_VALID[1], abs_tol=settings.REMOTE_TOLERANCE):
        return 1
    elif isclose(highest, settings.REMOTE_VALID[2], abs_tol=settings.REMOTE_TOLERANCE):
        return 2
    elif isclose(highest, settings.REMOTE_VALID[3], abs_tol=settings.REMOTE_TOLERANCE):
        return 3
    else:
        return None

def fft_convolve(a, b):
    # Must use numpy arrays, with sizes the power of 2 that match each other.
    a = np.fft.fft(a)
    b = np.fft.fft(b)
    inverse_fft = np.fft.ifft(a[0] * b[0])
    return inverse_fft[0]


def remote_detect(now):
    global samples, remote_sample_time, remote_high_pass, padded_filter
    now = time.monotonic()
    mic.record(samples, settings.REMOTE_SAMPLE_SIZE)  # Capture samples

    # Technique 1 Apply filter using np.convolve with slice to sample size
    filtered_samples = np.convolve(np.array(samples), settings.FILTER)
    overage = round((len(filtered_samples) - settings.REMOTE_SAMPLE_SIZE) / 2)
    filtered_samples = filtered_samples[overage:len(filtered_samples) - overage]

    # Technique 2 FFT based convolve
    #filtered_samples = np.array(fft_convolve(np.array(samples), padded_filter))

    # Technique 3 Slice instead of high_pass filter
    #filtered_samples = np.array(samples)
    #filtered_samples[:remote_high_pass] = 0

    #filtered_samples = np.array(samples[remote_high_pass:])

    # Perform FFT
    #fft_results = perform_fft(filtered_samples)
    fft_results = spectrogram(filtered_samples)

    # Remove 2nd half (data is symmetrical)
    fft_results = fft_results[round(len(fft_results) / 2):]

    #lowest_energy = np.min(fft_results)
    #median_energy = np.median(fft_results)
    highest_energy = np.max(fft_results)

    if (
            now - remote_sample_time > settings.REMOTE_SAMPLE_RATE
            and highest_energy > settings.REMOTE_THRESHOLD
    ):
        highest_address = np.argmax(fft_results)

        # Plotter code for debug
        # for i, _a in enumerate(fft_results):
        #    print((lowest_energy, median_energy, highest_energy, _a))
        #    time.sleep(0.02)

        print("highest_address:", highest_address, "| highest_energy:", highest_energy, "processing time=",time.monotonic() - now)

        remote_sample_time = now
        remote_button = determine_button(highest_address)
        if remote_button is not None:
            print("button:", remote_button)
            return remote_button

# Debug
#while True:
#    now = time.monotonic()
#    remote_detect(now)
