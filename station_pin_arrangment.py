import numpy as np
import math

st_arrange = np.arange(1, 163, 1)
stations_per_pin = 8

pin_clock_cycle = np.zeros((math.ceil(len(st_arrange)/stations_per_pin), stations_per_pin), np.int16)
for i in range(len(st_arrange)):
    pin_clock_cycle[int(i / 8)][int(i % 8)] = st_arrange[i]

print(pin_clock_cycle)