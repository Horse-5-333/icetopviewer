import numpy as np
import math
import time
import RPi.GPIO as gp

def get_frame_index(current_time: np.float32):
    return np.searchsorted(avg_time, current_time, "right")

def wait_until(final: np.float32):
    now = time.perf_counter()
    while now < final:
        now = time.perf_counter()
    return

############## DATA READING AND SANITIZATION ###############

data = np.loadtxt("./data/12362_000030_5.txt")
pin_clock_table = np.loadtxt("81_pin_table.txt")
clock_bits = np.loadtxt("clock_bits.txt").astype(int)

time_scale = 10
stations_per_pin = 8  # max 8
clock_freq = 400


cycle_period = 1 / clock_freq

# Normalize raw data
stations = data[:, 0]
doms = data[:, 1] - 60
energy = data[:, 2] / np.max(data[:, 2])
times = (data[:, 3] - np.min(data[:, 3])) / np.max(data[:, 3] - np.min(data[:, 3]))

# Compute average time and energy per station
avg_time = []
avg_energy = []
for st in np.unique(stations):
    station_mask = stations == st
    avg_time.append(np.mean(times[station_mask]))
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

clock_pins = [17, 27, 22] # GPIO17, 27, 22
data_pins = [4,26,3,10,9,11,5,6,13,19,14,15,18,23,24,25,8,1,12,16,20,21]
# 14 data pins × 8 channels = 112 addressable LEDs

########## WRITE LOOKUP TABLE ########

# 3D array: [pin group][channel][frame]
energy_array = np.zeros((pin_clock_table.shape[0], 8, stations.shape[0] + 1), np.float32)

for i, st in enumerate(stations):
    energy_array[:, :, i] = energy_array[:, :, i - 1]  # carry forward previous frame
    x, y = np.argwhere(pin_clock_table == st)[0]  # locate station in pin table
    energy_array[x, y, i] = avg_energy[i] * 100
    # set brightness for current station change, as only 1 station changes per frame


# cache saved array to skip generation if exists
np.save("./data/energy_array_12362_000030_5.npy", energy_array)

############# SIMULATION RUN ##########
gp.setmode(gp.BCM)
gp.setup(clock_pins, gp.OUT)

used_pins_num = data_pins[:math.ceil(len(stations)/8)]
print(used_pins_num)
data_pwm_pins = []
gp.setup(used_pins_num, gp.OUT)
for pin in used_pins_num:
    pwm = gp.PWM(pin, 3000)
    data_pwm_pins.append(pwm)
    pwm.start(0)
    

step = 0
total_steps = clock_freq * time_scale
output_levels = [0, 0, 0, 0, 0, 0, 0, 0]

print("startin!")

#neccesary to keep in synch with PWM
next_time = time.perf_counter() + cycle_period
while step <= total_steps:

    
    channel = int(step % 8)
    frame = get_frame_index(step / total_steps)
    output_levels = energy_array[:, channel, frame]
    
    for i, pwm in enumerate(data_pwm_pins):
        pwm.ChangeDutyCycle(0)
    wait_until(time.perf_counter() + (cycle_period/3))
    # waits for a proportion of the cycle to prevent overlap
    # n = 10 is a good spot for 400 hz
    gp.output(clock_pins, clock_bits[channel, :].tolist())
    for i, pwm in enumerate(data_pwm_pins):
        pwm.ChangeDutyCycle(100 if output_levels[i] > 0 else 0)
    
        
    
    wait_until(next_time)
    next_time += cycle_period
    step += 1
gp.cleanup()
