import numpy as np
import time
import RPi.GPIO as gp
import pigpio
from tkinter.filedialog import askopenfilename
from tkinter import Tk

gp.setwarnings(False)

def get_frame_index(current_time: np.float32):
    return np.searchsorted(avg_time, current_time, "right")

def wait_until(final: np.float32):
    now = time.perf_counter()
    while now < final:
        now = time.perf_counter()
    return



finished = False

############## DATA READING AND SANITIZATION ###############

# data = np.loadtxt("./data/12362_000030_6.txt")

Tk().withdraw()
data = np.loadtxt(askopenfilename())
pin_clock_table = np.loadtxt("81_pin_table.txt")
clock_bits = np.loadtxt("clock_bits.txt").astype(int)

time_scale = float(input("how long do you want this to take?(in seconds) \n"))
clock_freq = 6000
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
# We can use more

########## WRITE LOOKUP TABLE ########

# 3D array: [pin group][channel][frame]
energy_array = np.zeros((pin_clock_table.shape[0], 8, stations.shape[0] + 1), np.float32)

for i, st in enumerate(stations):
    energy_array[:, :, i] = energy_array[:, :, i - 1]  # carry forward previous frame
    x, y = np.argwhere(pin_clock_table == st)[0]  # locate station in pin table
    energy_array[x, y, i] = avg_energy[i] * 255
    # set brightness for current station change, as only 1 station changes per frame
    
energy_array[:, :, -1] = energy_array[:, :, -2]


# cache saved array to skip generation if exists
# np.save("./data/energy_array_12362_000030_5.npy", energy_array)

############# SIMULATION RUN ##########
# gp.setmode(gp.BCM)
pi = pigpio.pi()
# gp.setup(clock_pins, gp.OUT)
for pin in clock_pins:
    pi.set_mode(pin, pigpio.OUTPUT)

used_pins_num = data_pins[:11]
data_pwm_pins = []
# gp.setup(used_pins_num, gp.OUT)
for pin in used_pins_num:
    # pwm = gp.PWM(pin, 3000)
    pi.set_PWM_frequency(pin, 3000)
    # data_pwm_pins.append(pwm)
    # pwm.start(0)
    

step = 0
total_steps = clock_freq * time_scale
output_levels = np.zeros(len(data_pins), np.float32)

print("startin!")

#neccesary to keep in synch with PWM
print("Press CTRL+C to terminate.")
next_time = time.perf_counter() + cycle_period
debug_expected_finish = time.perf_counter() + time_scale
debug_start_time = time.perf_counter()
try:
    while step <= total_steps:
        # debug_time_elapsed = time.perf_counter()
        channel = int(step % 8)
        frame = get_frame_index(step / total_steps)
        output_levels = energy_array[:, channel, frame]
        
        for i, pin in enumerate(used_pins_num):
            pi.set_PWM_dutycycle(pin, 0)
            
        
        # waits for a proportion of the cycle to prevent overlap
        wait_until(time.perf_counter() + (cycle_period/10))
        
        # this is the clock going to the pins
        for i, pin in enumerate(clock_pins):
            pi.write(pin, clock_bits[channel, i])
        
        for i, pin in enumerate(used_pins_num):
            pi.set_PWM_dutycycle(pin, output_levels[i])
            
        
        wait_until(next_time)
        next_time += cycle_period
        
        # CLOCK DEBUG #
        #clock = [pi.read(clock_pins[0]), pi.read(clock_pins[1]), pi.read(clock_pins[2])]
        #print(clock)
        
        step += 1
        
#        if finished == False:
#            if step / total_steps > 1:
#                print("program done use keboard inturupt. ")
#                finished = True
                
        # debug_time_elapsed = time.perf_counter() - debug_time_elapsed
        # print("expected " + str(cycle_period * 1000) + "ms, got " + str(debug_time_elapsed * 1000))
        
except KeyboardInterrupt:
    pass

print("Took " + str(round(((time.perf_counter() - (cycle_period) - debug_start_time) - time_scale) * 1000, 2)) +
      "ms (" + str(round(((time.perf_counter() - (cycle_period) - debug_start_time) - time_scale)*100 /(time_scale), 2)) +
      "%) longer than expected. Avg " + str(round((time.perf_counter() - (cycle_period) - debug_start_time)*1000/total_steps, 2)) +
      "ms per cycle, expected " + str(round(cycle_period*1000, 2)) + "ms to keep time.")

for i, pin in enumerate(used_pins_num):
    pi.set_PWM_dutycycle(pin, 0)
