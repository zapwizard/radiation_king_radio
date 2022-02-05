
# Code prototype for ultrasonic PDM microphone
# Waiting for a Circuitpython patch before development can continue

import board
import array
import audiobusio
import math
from ulab import numpy as np
from ulab.scipy.signal import spectrogram


#Ultrasonic Mic Related
threshold = 100
pdm_select = digitalio.DigitalInOut(board.GP2)
pdm_select.direction = digitalio.Direction.OUTPUT
pdm_select.value = False #Enable ultrasonic mode

sample_frequency = 21000
sample_size = 1024
mic = audiobusio.PDMIn(board.GP3, board.GP4, sample_rate=sample_frequency, bit_depth=8, mono=True)
print ("sample_size=",sample_size,"sample_frequency=",sample_frequency,"returned mic.sample_rate=",mic.sample_rate)
time_per_sample = None
samples = array.array('B', [1] * sample_size)
check = array.array('B', [1] * sample_size)

def benchmark_capture():
    global sample_frequency, sample_size, time_per_sample
    start_capture_time = time.monotonic_ns()
    mic.record(samples, len(samples))
    if samples == check:
        print("Failed to capture samples")
    else:
        sample_duration = time.monotonic_ns() - start_capture_time
        time_per_sample = sample_duration / sample_size
        if time_per_sample:
            sample_frequency = round((1 / time_per_sample) * 10**9)
            print(sample_size, "samples took",sample_duration,"ns or", time_per_sample, "ns per sample", "| Max Sample Frequency =", sample_frequency)

#while True:
benchmark_capture()
    #time.sleep(5)


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
    results = real[1:len(real)] # Remove DC offset
    return results

def perform_spectrogram(samples):
    results = spectrogram(np.array(samples))
    results = results[1:len(results)] # Remove DC offset
    return results

def determine_energies(results):
    global threshold, hz_per_sample
    lowest_energy = round(abs(np.min(results)))
    if lowest_energy > threshold:
        highest_address = np.argmax(results) + 1 # Determine max energetic signal
        highest_frequency = highest_address * hz_per_sample # Get the frequency of the highest amplitude
        return highest_frequency

def determine_button(highest):
    if highest > 250000:
        print("4: Channel Lower", highest)
    elif highest > 70:
        print("3: Channel Lower", highest)
    elif highest > 30:
        print("2: Volume On/Off", highest)
    elif highest > 22000:
        print("1: Channel Higher", highest)
    else:
        print("Invalid", highest)

hz_per_sample = sample_frequency / sample_size
print("hz_per_sample=", hz_per_sample)
time.sleep(3)


mic.record(samples, len(samples))

#Perform FFT on samples
fft_results = perform_fft(samples)
#fft_results = perform_spectrogram(samples)

#Crop to upper frequencies:
fft_results = fft_results[round(len(fft_results)/2):len(fft_results)]

#Determine if samples are above threshold
lowest_energy = round(abs(np.min(fft_results)))

#if lowest_energy > threshold:

magnitude = normalized_rms(fft_results)

# Compute the highest average result:
highest_address = np.argmax(fft_results)
highest_frequency = round(highest_address * hz_per_sample) # Get the frequency of the highest amplitude

print(("lowest_energy",lowest_energy,"\t|avg magnitude",magnitude))
#"\t|highest_frequency",highest_frequency))

time.sleep(5)

