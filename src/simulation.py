import math
import numpy as np
import sounddevice as sd
import pandas as pd
from scipy.optimize import minimize
from scipy.optimize import minimize_scalar
import csv
import parselmouth
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
from scipy.signal import butter, lfilter

MAX_PENALTY = 1e5

def in2m(inches):
    return inches * 0.0254

class Guitar:
    def __init__(self, *args):
        if len(args) == 0:
            params = Guitar.measure_to_parameters(*Guitar.default_measurements())
        elif len(args) == 1:
            params = Guitar.reshape(args[0])
        else:
            params = args

        assert len(params) == 7

        i = 0
        self.r_str = params[i]; i += 1
        self.r_spr = params[i]; i += 1
        self.k_spr = params[i]; i += 1
        self.k_str = params[i]; i += 1
        self.T_str0 = params[i]; i += 1
        self.scale_length = params[i]; i += 1
        self.lin_mass_density = params[i]; i += 1

        self.T_spr0 = np.sum(self.T_str0) * self.r_str / self.r_spr
        self.k_str_total = np.sum(self.k_str)
            
    @classmethod 
    def default_measurements(cls):
        # Default guitar parameters
        scale_length = np.array([in2m(25.5), in2m(25.5), in2m(25.5), in2m(25.5), in2m(25.5), in2m(25.5)])  # 25.5 inches in meters
        r_str = 0.02  # lever arm to string force (e.g., 2 cm)
        r_spr = 0.04  # lever arm to spring force (e.g., 4 cm)
        E = 2.0e11  # Young's modulus for steel in Pa 11
        k_spr = 3 * 20000.0  # Total spring constant in N/m (3 springs at 20 N/mm each)
        string_density = 7850.0 # density of steel ~7850 kg/m^3
        balanced_freq = np.array([329.63, 246.94, 196.00, 146.83, 110.00, 82.41])
        diameters = np.array([in2m(0.010), in2m(0.013), in2m(0.017), in2m(0.026), in2m(0.036), in2m(0.046)])
        return r_str, r_spr, E, k_spr, string_density, scale_length, balanced_freq, diameters      

    @classmethod
    def measure_to_parameters(cls, r_str, r_spr, E, k_spr, string_density, scale_length, balanced_freq, diameters):
        # Compressed guitar parameters
        lever_ratio = r_str / r_spr

        # derive mu and k (string linear mass density and string stiffness constant)
        lin_mass_density = [0] * 6
        k_str = [0] * 6
        for i in range(6):
            diameter = diameters[i]
            area = math.pi * (diameter / 2)**2
            lin_mass_density[i] = area * string_density
            k_str[i] = E * area / scale_length[i]

        # Calculate intitial tension assuming bridge is centered at tuned state
        T_str0 = [0] * 6
        for i in range(6):
            T_str0[i] = (2 * scale_length[i] * balanced_freq[i])**2 * lin_mass_density[i]

        T_spr0 = sum(T_str0) * r_str / r_spr
        return r_str, r_spr, k_spr, k_str, T_str0, scale_length, lin_mass_density

    def to_list(self):
        return [
            self.r_str,
            self.r_spr,
            self.k_spr,
            self.k_str,
            self.T_str0,
            self.scale_length,
            self.lin_mass_density
        ]

    def flatten(self):
        x = np.array(
            [self.r_str] +
            [self.r_spr] +
            [self.k_spr] +
            list(self.k_str) +
            list(self.T_str0) +
            list(self.scale_length) +
            list(self.lin_mass_density)
        )
        return x

    @classmethod
    def reshape(cls, arr):
        assert len(arr) == 27
        return arr[0], arr[1], arr[2], arr[3:3+6], arr[9:9+6], arr[15:15+6], arr[21:21+6]

def find_equilibrium(current_offsets, guitar):
    spring_term = guitar.k_spr * (guitar.r_str / guitar.r_spr) * guitar.r_spr
    modified_tension = sum(guitar.T_str0 + guitar.k_str * current_offsets)
    x = (
        (guitar.r_spr * guitar.T_spr0 - guitar.r_str * modified_tension) 
        /
        (guitar.r_spr * guitar.k_spr + guitar.r_str * guitar.k_str_total)
    )
    return x

def calculate_frequencies(x_eq, current_offsets, guitar):
    calculated_freqs = np.zeros(6)
    
    for i in range(6):
        L_new = guitar.scale_length[i] + x_eq
        T_new = guitar.T_str0[i] + guitar.k_str[i] * (x_eq + current_offsets[i])
        
        if T_new < 0 or guitar.lin_mass_density[i] < 0:
            return None

        freq = (1 / (2 * L_new)) * math.sqrt(T_new / guitar.lin_mass_density[i])
        calculated_freqs[i] = freq
        
    return calculated_freqs

def objective_function(current_offsets, target_freq, guitar):
    x_eq = find_equilibrium(current_offsets, guitar)
    calculated_freqs = calculate_frequencies(x_eq, current_offsets, guitar)
    if calculated_freqs is None:
        return MAX_PENALTY
    # Sum of squared differences between calculated and target frequencies
    error = sum((calculated_freqs[i] - target_freq[i])**2 for i in range(6))
    return error

def tune_all_targets(target_freq, guitar, initial_offset=None):
    initial_offset = initial_offset or [0] * 6

    # Run optimization
    result = minimize(
        lambda x: objective_function(x, target_freq, guitar), 
        initial_offset, 
        method='Nelder-Mead',
        options={
            'maxiter': 10000,
            'maxfev': 20000,
            'xatol': 1e-16,
            'fatol': 1e-16,
            'disp': False
        }
    )
    
    return result.x

def single_objective_function(current_offsets, str_n, target_freq, guitar):
    x_eq = find_equilibrium(current_offsets, guitar)
    calculated_freqs = calculate_frequencies(x_eq, current_offsets, guitar)
    if calculated_freqs is None:
        return MAX_PENALTY
    
    # Sum of squared differences between calculated and target frequencies
    error = (calculated_freqs[str_n] - target_freq)**2 
    
    return error

def tune_one_target(target_freq, str_n, guitar, initial_offset):
    # Run optimization
    
    def cost(offset):
        current_offsets = initial_offset.copy()
        current_offsets[str_n] = offset
        return single_objective_function(current_offsets, str_n, target_freq, guitar)

    a = initial_offset[str_n] - 0.001 
    b = initial_offset[str_n] + 0.001

    result = minimize_scalar(
        cost,
        method='bounded',
        bounds=(a, b),
        options={
            'xatol': 1e-16, 
            'maxiter': 1000
        }
    )

    ret = initial_offset.copy()
    ret[str_n] = result.x

    return ret

def play_tuned_strings(freqs):
    for i in range(6):
        freq = freqs[i]
        print(f"Playing String {i+1} at {freq:.2f} Hz")
        note = karplus_strong(freq=freq, duration=1.0, decay=0.99, brightness=0.8, volume=0.5)
        sd.play(note, samplerate=44100)
        sd.wait()

# Assume data is generated by turning string 1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6, ...
def generate_artificial_data(real_data, guitar):
    starting_freq = real_data[0]
    #print('T_str0 ', guitar.T_str0)
    offsets = tune_all_targets(starting_freq, guitar)
    starting_x = find_equilibrium(offsets, guitar)
    freq0 = calculate_frequencies(starting_x, offsets, guitar)
    if any(x == 0 for x in freq0):
        return None

    str_n = 0
    ret = [freq0]
    for real_freq in real_data[1:]:
        target_freq = real_freq[str_n]
        new_offsets = tune_one_target(target_freq, str_n, guitar, offsets)

        new_x = find_equilibrium(new_offsets, guitar)
        new_freq = calculate_frequencies(new_x, new_offsets, guitar)
        if any(x == 0 for x in new_freq):
            return None

        ret.append(new_freq)

        offsets = new_offsets

        str_n = (str_n + 1) % 6

    return ret

def cost1(real_data, guitar):
    total_cost = 0

    starting_freq = real_data[0]
    #print('T_str0 ', guitar.T_str0)
    offsets = tune_all_targets(starting_freq, guitar)
    starting_x = find_equilibrium(offsets, guitar)
    freq0 = calculate_frequencies(starting_x, offsets, guitar)
    if freq0 is None:
        return MAX_PENALTY
    total_cost += np.sum((np.array(starting_freq) - np.array(freq0))**2)

    str_n = 0
    for real_freq in real_data[1:]:
        target_freq = real_freq[str_n]
        new_offsets = tune_one_target(target_freq, str_n, guitar, offsets)

        new_x = find_equilibrium(new_offsets, guitar)
        new_freq = calculate_frequencies(new_x, new_offsets, guitar)
        if new_freq is None:
            return MAX_PENALTY
        total_cost += np.sum((np.array(real_freq) - np.array(new_freq))**2)

        offsets = new_offsets

        str_n = (str_n + 1) % 6

    return total_cost / len(real_data)

def cost2(real_data, guitar):
    total_cost = 0

    starting_freq = real_data[-1]
    #print('T_str0 ', guitar.T_str0)
    offsets = tune_all_targets(starting_freq, guitar)
    starting_x = find_equilibrium(offsets, guitar)
    freq0 = calculate_frequencies(starting_x, offsets, guitar)
    if freq0 is None:
        return MAX_PENALTY
    total_cost += np.sum((np.array(starting_freq) - np.array(freq0))**2)

    str_n = (len(real_data) - 2) % 6
    for real_freq in real_data[-2::-1]:
        target_freq = real_freq[str_n]
        new_offsets = tune_one_target(target_freq, str_n, guitar, offsets)

        new_x = find_equilibrium(new_offsets, guitar)
        new_freq = calculate_frequencies(new_x, new_offsets, guitar)
        if new_freq is None:
            return MAX_PENALTY
        total_cost += np.sum((np.array(real_freq) - np.array(new_freq))**2)

        offsets = new_offsets

        str_n = (str_n - 1) % 6

    return total_cost / len(real_data)

def cost3(real_data, guitar):
    total_cost = 0
    for real_freq in real_data:
        new_offsets = tune_all_targets(real_freq, guitar)
        new_x = find_equilibrium(new_offsets, guitar)
        new_freq = calculate_frequencies(new_x, new_offsets, guitar)
        if new_freq is None:
            return MAX_PENALTY
        total_cost += np.sum((np.array(real_freq) - np.array(new_freq))**2)
        offsets = new_offsets

    return total_cost / len(real_data)



def generate_artificial_data_reversed(real_data, guitar):
    starting_freq = real_data[0]
    offsets = tune_all_targets(starting_freq, guitar)
    starting_x = find_equilibrium(offsets, guitar)
    freq0 = calculate_frequencies(starting_x, offsets, guitar)
    if freq0 is None:
        return None

    str_n = len(real_data) - 2
    ret = [freq0]
    for real_freq in real_data[:0:-1]:
        target_freq = real_freq[str_n]
        new_offsets = tune_one_target(target_freq, str_n, guitar, offsets)

        new_x = find_equilibrium(new_offsets, guitar)
        new_freq = calculate_frequencies(new_x, new_offsets, guitar)
        if new_freq is None:
            return None

        ret.append(new_freq)

        offsets = new_offsets

        str_n = (str_n - 1) % 6

    return ret

def compare_data(data1, data2):
    total = 0
    for i in range(len(data1)):
        for j in range(len(data1[i])):
            total += (data1[i][j] - data2[i][j])**2
    return total / len(data1)

def parameter_objective_function(parameters, real_data):
    guitar = Guitar(parameters)
    #guitar = Guitar.parameters_to_guitar(*reshape(parameters))
    #artificial_data = generate_artificial_data(real_data, guitar)
    # if artificial_data is None:
    #     return MAX_PENALTY
    #compare_data(artificial_data, real_data)
    return (cost1(real_data, guitar) + cost2(real_data, guitar) + cost3(real_data, guitar))/3

def make_param_bounds():
    r_str, r_spr, k_spr, k_str, T_str0, scale_length, lin_mass_density = Guitar().to_list()

    # Bounds: ±20% for physical parameters
    def around(val, pct=0.05): return (val * (1 - pct), val * (1 + pct))

    bounds = [
        around(r_str, pct=0.8),               # r_str
        around(r_spr, pct=0.8),              # r_spr
        around(k_spr, pct=0.8),              # k_spr
    ]

    bounds += [around(k, pct=0.8) for k in k_str]               # k_str (per string)
    bounds += [around(T, pct=0.8) for T in T_str0]              # T_str0 (per string)
    bounds += [around(L, pct=0.8) for L in scale_length]        # scale_length (per string)
    bounds += [around(mu, pct=0.8) for mu in lin_mass_density]  # lin_mass_density (per string)

    return bounds


def optimize_parameters(real_data):
    initial_params = Guitar().flatten()
    param_bounds = make_param_bounds()

    result = minimize(
        lambda x: parameter_objective_function(x, real_data),
        initial_params,
        method='L-BFGS-B',  
        bounds=param_bounds,
        options={
            'disp': True,
            'maxiter': 40,
            'gtol': 1e-8,   
            'ftol': 1e-10    
        }
    )

    return result.x

def calibrate():
    real_data = None
    with open('pitches.csv', 'r') as f:
        reader = csv.reader(f)
        real_data = [list(map(float, row)) for row in reader]
    if real_data:
        #print(real_data)
        params = optimize_parameters(real_data)
        guitar = Guitar(params)

        with open('optimized_params.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(params)
    return guitar

def test_parameters():
    #guitar = Guitar.reshape([0.02000000013690754,0.04000000007329067,59999.99999994744,15646.363008578479,26442.35306966615,45217.98254486209,105769.41671069965,202776.87047246404,331077.04965326306,79.7775738270039,73.25989093353991,80.3693782945096,105.01757741825557,115.13774920700575,90.91631933677286,0.7124644969267925,0.71247,0.58293,0.58293,0.71247,0.5829357468804054,0.00037787710253695884,0.00070583465100193,0.0010920648263318114,0.0025544492131498414,0.005412791169813617,0.008225759199319156])
    guitar = Guitar([0.004192943344892194,0.0527210733243767,60000.00002754921,15646.363451143618,26442.354190429935,45217.99026649949,105769.4166681145,202776.86981479632,331077.04979176837,72.52514720114756,68.78669744260682,74.10451752256648,97.27716521435585,104.6707057014392,95.92022163385528,0.4714008471583247,0.8239609365225877,0.4713989423688511,0.4655332067198231,0.8298406813954923,0.4655924432686475,0.00018279946433012137,0.000134444695428939,0.0006431422682395684,0.004840009035441805,0.002416111700068022,0.009151670624607467])
    real_data = None
    with open('pitches.csv', 'r') as f:
        reader = csv.reader(f)
        real_data = [list(map(float, row)) for row in reader]
    if real_data:
        starting_freq = real_data[0]
        offsets = tune_all_targets(starting_freq, guitar)
        starting_x = find_equilibrium(offsets, guitar)
        freq0 = calculate_frequencies(starting_x, offsets, guitar)
        print('R', starting_freq)
        print('A', freq0)

        str_n = 0
        for real_freq in real_data[1:]:
            target_freq = real_freq[str_n]
            new_offsets = tune_one_target(target_freq, str_n, guitar, offsets)

            new_x = find_equilibrium(new_offsets, guitar)
            new_freq = calculate_frequencies(new_x, new_offsets, guitar)

            print('R', real_freq)
            print('A', new_freq)

            offsets = new_offsets

            str_n = (str_n + 1) % 6

#calibrate()
#test_parameters()