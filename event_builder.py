import numpy as np
import time
import pigpio
from tkinter.filedialog import askopenfilename
from tkinter import Tk

# Initialize pigpio
pi = pigpio.pi()
if not pi.connected:
    raise IOError("Could not connect to pigpio daemon")

# ==================== Data Loading ====================
Tk().withdraw()
data = np.loadtxt(askopenfilename())
pin_clock_table = np.loadtxt("81_pin_table.txt")
clock_bits = np.loadtxt("clock_bits.txt").astype(int)

# User input: total simulation duration (seconds)
user_time_scale = float(input("Simulation duration (seconds): "))
time_scale_adjusted = user_time_scale * 0.675
clock_freq = 256  # desired full-frame refresh rate (Hz)
cycle_period = 1.0 / clock_freq

# ================= Normalize and Average Data ================
# Raw columns: station, dom, energy, timestamp
stations_raw = data[:, 0]
doms = data[:, 1] - 60
energy_raw = data[:, 2]
time_raw = data[:, 3]

# Normalize energy (0-1) and time (0-1)
energy_norm = energy_raw / np.max(energy_raw)
time_norm = (time_raw - np.min(time_raw)) / np.ptp(time_raw)

# Compute per-station averages
unique_stations = np.unique(stations_raw)
avg_time = []
avg_energy = []
for st in unique_stations:
    mask = stations_raw == st
    avg_time.append(np.mean(time_norm[mask]))
    avg_energy.append(np.mean(energy_norm[mask]))
avg_time = np.array(avg_time)
avg_energy = np.array(avg_energy)

# Sort by avg_time
order = np.argsort(avg_time)
avg_time = avg_time[order]
stations = unique_stations[order]
avg_energy = avg_energy[order]

# Build energy lookup: [pin group][channel][frame]
frames = len(stations) + 1
rows = pin_clock_table.shape[0]
energy_array = np.zeros((rows, 8, frames), np.float32)
for i, st in enumerate(stations, start=1):
    energy_array[:, :, i] = energy_array[:, :, i - 1]
    x, y = np.argwhere(pin_clock_table == st)[0]
    energy_array[x, y, i] = avg_energy[order[i - 1]]
energy_array[:, :, 0] = 0  # initial blank frame

# ================= GPIO Setup =================
clock_pins = [17, 27, 22]  # demux select pins (BCM)
data_pins = [4, 26, 3, 10, 9, 11, 5, 6, 13, 19, 14, 15, 18, 23]
# PWM resolution period (microseconds) for each channel
pwm_period_us = int(1e6 / (clock_freq * 8))  # divide period across 8 channel pulses

for pin in clock_pins + data_pins:
    pi.set_mode(pin, pigpio.OUTPUT)

# ================= Helper Functions =================
def get_frame_index(t_norm: float) -> int:
    """
    Return frame index for normalized time t_norm (0-1).
    """
    return int(np.searchsorted(avg_time, t_norm, side='right'))


def wait_until(target: float):
    """
    Busy-wait until time.perf_counter() reaches target.
    """
    while time.perf_counter() < target:
        pass


def build_full_mux_wave(frame_idx: int) -> list:
    """
    Build pigpio.pulse list that sequentially pulses all 8 channels
    with duty cycles from energy_array[..., frame_idx].
    """
    pulses = []
    for channel in range(8):
        # Extract brightness levels for this channel
        levels = energy_array[:, channel, frame_idx]
        # Calculate on/off durations per pin
        on_times = (levels * pwm_period_us).astype(int)
        off_times = pwm_period_us - on_times

        # Create pulses for data pins
        mask_on = 0
        mask_off = 0
        for pin, on_t in zip(data_pins, on_times):
            if on_t > 0:
                mask_on |= (1 << pin)
            if on_t < pwm_period_us:
                mask_off |= (1 << pin)
        # Add on/off pulses for this channel period
        pulses.append(pigpio.pulse(mask_on, 0, np.max(on_times)))
        pulses.append(pigpio.pulse(0, mask_on, pwm_period_us - np.max(on_times)))

        # Set demux lines for next channel
        clk_bits = clock_bits[channel]
        clk_on = sum((1 << p) for p, b in zip(clock_pins, clk_bits) if b)
        clk_off = sum((1 << p) for p, b in zip(clock_pins, clk_bits) if not b)
        pulses.append(pigpio.pulse(clk_on, clk_off, 50))  # short latch pulse

    return pulses

# ================= Main Loop =================
step = 0
total_steps = int(clock_freq * time_scale_adjusted)
cycle_period = time_scale_adjusted / total_steps
next_time = time.perf_counter() + cycle_period

debug_start_time = time.perf_counter()
debug_missed_cycles = 0

try:
    while step <= total_steps:
        # Determine current frame based on normalized time progress
        t_norm = step / total_steps
        frame = get_frame_index(t_norm)

        # Build and send waveform for full 8-channel refresh
        pi.wave_clear()
        wave = build_full_mux_wave(frame)
        pi.wave_add_generic(wave)

        wid = pi.wave_create()
        if wid >= 0:
            pi.wave_send_once(wid)
            # Wait until wave is done
            while pi.wave_tx_busy():
                pass
            pi.wave_delete(wid)
            
        step += 1
        now = time.perf_counter()
        if now > next_time:
            debug_missed_cycles += 1
            next_time += cycle_period
            continue

        # wait until the next step time - almost never happpens, as the system consistently
        # runs over cycle deadline (but still looks smooth)
        wait_until(next_time)
        next_time += cycle_period
        

except KeyboardInterrupt:
    pass

actual_duration = time.perf_counter() - debug_start_time
expected_duration = user_time_scale
extra_time_ms = round((actual_duration - expected_duration) * 1000, 3)
extra_time_pct = round((actual_duration - expected_duration) * 100 / expected_duration, 3)
avg_cycle_time_ms = round((actual_duration * 1000) / total_steps, 3)
expected_cycle_time_ms = round((expected_duration * 1000) / total_steps, 3)
missed_pct = round(debug_missed_cycles * 100 / total_steps, 3)

print(
    f"Took {extra_time_ms}ms ({extra_time_pct}%) longer than expected. "
    f"Avg {avg_cycle_time_ms}ms per cycle, expected {expected_cycle_time_ms}ms to keep time. "
    f"{debug_missed_cycles}/{int(total_steps)} ({missed_pct}%) missed cycles."
)

# Cleanup: turn off all outputs
for pin in data_pins + clock_pins:
    pi.write(pin, 0)
pi.stop()
