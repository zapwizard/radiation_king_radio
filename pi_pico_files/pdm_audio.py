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
remote_pass_start = round(
    map_range(settings.REMOTE_FREQ_MIN, 0, settings.REMOTE_SAMPLE_FREQUENCY, 0, settings.REMOTE_SAMPLE_SIZE))
remote_pass_end = round(
    map_range(settings.REMOTE_FREQ_MAX, 0, settings.REMOTE_SAMPLE_FREQUENCY, 0, settings.REMOTE_SAMPLE_SIZE))


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


def spectrogram_half(data):
    data = spectrogram(data)
    # Remove 2nd half (data is symmetrical)
    return data[round(data.size / 2):]


def plot_data(data_to_plot):
    highest_value = np.max(data_to_plot)
    lowest_value = np.min(data_to_plot)
    for i, x in enumerate(data_to_plot):
        print((lowest_value, highest_value, x))
        time.sleep(0.02)


def convolve_data(a, b, size):
    convolved = np.convolve(np.array(a), b)
    overage = round((len(convolved) - size) / 2)
    return convolved[overage:len(convolved) - overage]


# Expand the filter to REMOTE_SAMPLE_SIZE
filter_expanded = np.ones(settings.REMOTE_SAMPLE_SIZE)
filter_expanded = np.convolve(filter_expanded, settings.FILTER)
overage = round((len(filter_expanded) - settings.REMOTE_SAMPLE_SIZE) / 2)
filter_expanded = filter_expanded[overage:len(filter_expanded) - overage]


def compare_methods(now):
    global samples, remote_sample_time, remote_pass_start, remote_pass_end, filter_expanded
    mic.record(samples, settings.REMOTE_SAMPLE_SIZE)  # Capture samples

    # Apply filter using np.convolve with slice to sample size
    convolve_time = time.monotonic()  # debug processing time
    convolve_samples = convolve_data(samples, settings.FILTER, settings.REMOTE_SAMPLE_SIZE)
    convolve_results = spectrogram_half(convolve_samples)
    convolve_duration = time.monotonic() - convolve_time

    # Pre-expanded filter
    multiplication_time = time.monotonic()  # debug processing time
    multiplication_samples = filter_expanded * samples
    multiplication_results = spectrogram_half(multiplication_samples)
    multiplication_duration = time.monotonic() - multiplication_time

    highest_energy = np.max(convolve_results)
    if (
            highest_energy > settings.REMOTE_THRESHOLD
            or now - remote_sample_time > settings.REMOTE_SAMPLE_RATE
    ):

        plot_data(convolve_results)
        for x in range(5):
            print((10, 10, 10))
        plot_data(multiplication_results)
        print("Convolve Technique took:", convolve_duration)
        print("Multiplication took:", multiplication_duration)

        remote_sample_time = now
        for _ in range(15):
            print((0, 0, 0))


def remote_detect(now):
    global samples, remote_sample_time, remote_pass_start, remote_pass_end, filter_expanded
    mic.record(samples, settings.REMOTE_SAMPLE_SIZE)  # Capture samples

    # Apply filter using np.convolve with slice to sample size
    convolve_time = time.monotonic()  # debug processing time
    convolve_samples = convolve_data(samples, settings.FILTER, settings.REMOTE_SAMPLE_SIZE)
    convolve_results = spectrogram_half(convolve_samples)
    convolve_duration = time.monotonic() - convolve_time

    highest_energy = np.max(convolve_results)
    if (
            now - remote_sample_time > settings.REMOTE_SAMPLE_RATE
            and highest_energy > settings.REMOTE_THRESHOLD
    ):
        highest_address = np.argmax(convolve_results)
        print("highest_address:", highest_address, "| highest_energy:", highest_energy, "processing time=",convolve_duration)

        remote_sample_time = now
        remote_button = determine_button(highest_address)
        highest_energy = None
        if remote_button is not None:
            #print("button:", remote_button)
            return remote_button

# Debug
# while True:
# now = time.monotonic()
# remote_detect(now)
