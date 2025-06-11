import numpy as np
import math
from time import sleep  # Unused, but kept in case re-enabled

def get_frame_index(current_time: np.float32):
    return np.searchsorted(avg_time, current_time, "right")

############## DATA READING AND SANITIZATION ###############

data = np.loadtxt("./data/12362_000030_5.txt")
pin_clock_table = np.loadtxt("81_pin_table.txt")

time_scale = 10
stations_per_pin = 8  # max 8
clock_freq = 180

# Normalize raw data
stations = data[:, 0]
doms = data[:, 1] - 60
energy = data[:, 2] / np.max(data[:, 2])
time = (data[:, 3] - np.min(data[:, 3])) / np.max(data[:, 3] - np.min(data[:, 3]))

# Compute average time and energy per station
avg_time = []
avg_energy = []
for st in np.unique(stations):
    station_mask = stations == st
    avg_time.append(np.mean(time[station_mask]))
    avg_energy.append(np.mean(energy[station_mask]))

stations = np.unique(stations)
avg_time = np.array(avg_time)
avg_energy = np.array(avg_energy)

# Sort all arrays by time
time_key = np.argsort(avg_time)
avg_time = avg_time[time_key]
stations = stations[time_key]
avg_energy = avg_energy[time_key]

# Create dictionary of per-station readings
station_readings = {}
for i in range(len(stations)):
    station_readings[stations[i]] = {"energy": avg_energy[i], "time": avg_time[i]}

###################### PINS AND SETUP ########################

clock_pins = [7, 0, 2]  # GPIO 4, 17, 27
data_pins = [3, 21, 22, 23, 24, 25, 1, 4, 5, 6, 26, 27, 28, 29]
# 14 data pins × 8 channels = 112 addressable LEDs

########## WRITE LOOKUP TABLE ########

# 3D array: [pin group][channel][frame]
energy_array = np.zeros((pin_clock_table.shape[0], 8, stations.shape[0] + 1), np.float32)

for i, st in enumerate(stations):
    energy_array[:, :, i] = energy_array[:, :, i - 1]  # carry forward previous frame
    x, y = np.argwhere(pin_clock_table == st)[0]  # locate station in pin table
    energy_array[x, y, i] = avg_energy[i]
    # set brightness for current station change, as only 1 station changes per frame


# cache saved array to skip generation if exists
np.save("./data/energy_array_12362_000030_5.npy", energy_array)

############# SIMULATION RUN ##########
step = 0
total_steps = clock_freq * time_scale
#
# while step <= total_steps:
#     channel = int(step % 8)
#     frame = get_frame_index(step / total_steps)
#     output_levels = energy_array[:, channel, frame]
#
#     #sleep(1 / clock_freq)  # re-enable if running in real time
#     step += 1