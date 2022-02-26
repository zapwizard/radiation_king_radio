# Modified from https://fiiir.com/
# Run this on a computer with full python (No pi Pico) to re-calculate the window

from __future__ import print_function
from __future__ import division

import numpy as np

# Example code, computes the coefficients of a high-pass windowed-sinc filter.

# Configuration.
fS = 82000  # Sampling rate.
fH = 31000  # Cutoff frequency.
N = 512  # Filter length

# Compute sinc filter.
h = np.sinc(2 * fH / fS * (np.arange(N) - (N - 1) / 2))

# Calculate window.
window = np.blackman(N+1)

# crop window
window = window[0:N]

# Write to file
f = open("window.txt", "a")
for i, x in enumerate(window):
    f.write(str(x))
    f.write(",\n")
f.close()

# Apply window

h *= window

# Normalize to get unity gain.
h /= np.sum(h)

# Create a high-pass filter from the low-pass filter through spectral inversion.
h = -h
h[(N - 1) // 2] += 1
print("*")
print(h)

# Applying the filter to a signal s can be as simple as writing
# s = np.convolve(s, h)