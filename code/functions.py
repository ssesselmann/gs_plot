import pyaudio
import webbrowser
import wave
import numpy as np
import subprocess
import math
import csv
import json
import time
import os
import platform
import sqlite3 as sql
import pandas as pd
from scipy.signal import find_peaks, peak_widths
from collections import defaultdict
from datetime import datetime
from urllib.request import urlopen

cps_list = []

data_directory  = os.path.join(os.path.expanduser("~"), "impulse_data")

# Finds pulses in string of data over a given threshold
def find_pulses(left_channel):
    samples =[]
    pulses = []
    for i in range(len(left_channel) - 51):
        samples = left_channel[i:i+51]  # Get the first 51 samples
        if samples[25] >= max(samples) and (max(samples)-min(samples)) > 100 and samples[25] < 32768:
            pulses.append(samples)
    if len(pulses) != 0:  # If the list is empty
        next       
    return pulses   

# Calculates the average pulse shape
def average_pulse(sum_pulse, count):       
    average = []
    for x in sum_pulse:
        average.append(x / count)
    return average 

    # Normalises the average pulse shape
def normalise_pulse(average):
    normalised = []
    mean = sum(average) / len(average)   
    normalised = [n - mean for n in average]  
    normalised_int = [int(x) for x in normalised]
    return normalised_int

    # Normalised pulse samples less normalised shape samples squared summed and rooted
def distortion(normalised, shape):
    product = [(x - y)**2 for x, y in zip(shape, normalised)]
    distortion = int(math.sqrt(sum(product)))

    return distortion
    # Function calculates pulse height
def pulse_height(samples):
    return max(samples)-min(samples)

    # Function to create bin_array 
def create_bin_array(start, stop, bin_size):
    return np.arange(start, stop, bin_size)

def histogram_count(n, bins):
    # find the bin for the input number
    for i in range(len(bins)):
        if n < bins[i]:
            bin_num = i
            break
    else:
        bin_num = len(bins)
    return bin_num

    #Function to bin pulse height
def update_bin(n, bins, bin_counts):
    bin_num = histogram_count(n, bins)
    bin_counts[bin_num] += 1
    return bin_counts

# This function writes a 2D histogram to JSON file according to NPESv1 schema.
def write_histogram_json(t0, t1, bins, counts, elapsed, name, histogram, coeff_1, coeff_2, coeff_3):
    
    jsonfile = get_path(f'{data_directory}/{name}.json')
    data =  {"schemaVersion":"NPESv1",
                "resultData":{
                    "startTime": t0.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "endTime": t1.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "energySpectrum":{
                        "numberOfChannels":bins,
                        "energyCalibration":{
                            "polynomialOrder":2,
                            "coefficients":[coeff_3,coeff_2,coeff_1]
                            },
                        "validPulseCount":counts,
                        "measurementTime": elapsed,
                        "spectrum": histogram
                        }
                    }
                }

    with open(jsonfile, "w+") as f:
        json.dump(data, f)

# This function writes 3D intervals to JSON file according to NPESv1 schema.
def write_3D_intervals_json(t0, t1, bins, counts, elapsed, filename, interval_number, coeff_1, coeff_2, coeff_3):

    jsonfile = get_path(f'{data_directory}/{filename}_3d.json')
    
    if not os.path.isfile(jsonfile):
        data = {
            "schemaVersion": "NPESv1",
            "resultData": {
                "startTime": t0.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                "endTime": t1.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                "energySpectrum": {
                    "numberOfChannels": bins,
                    "energyCalibration": {
                        "polynomialOrder": 2,
                        "coefficients": [coeff_3, coeff_2, coeff_1]
                    },
                    "validPulseCount": 0,
                    "measurementTime": 0,
                    "spectrum":[]
                }
            }
        }
    else:
        with open(jsonfile, "r") as f:
            data = json.load(f)

    # Update the existing values
    data["resultData"]["energySpectrum"]["validPulseCount"] = counts
    data["resultData"]["energySpectrum"]["measurementTime"] = elapsed
    data["resultData"]["energySpectrum"]["spectrum"].extend([interval_number])  # Wrap intervals in a list

    with open(jsonfile, "w") as f:
        json.dump(data, f)

def write_cps_json(name, cps):
    global cps_list
    jsonfile = get_path(f'{data_directory}/{name}-cps.json')
    cps_list.append(cps)
    data     = {'cps': cps_list }
    with open(jsonfile, "w+") as f:
        json.dump(data, f)
  
def clear_global_cps_list():
    global cps_list
    cps_list = []

# This function loads settings from sqli database
def load_settings():

    database = get_path(f'{data_directory}/.data.db')
    settings        = []
    conn            = sql.connect(database)
    c               = conn.cursor()
    query           = "SELECT * FROM settings "
    c.execute(query) 
    settings        = c.fetchall()[0]
    return settings

# This function opens the csv and loads the pulse shape  
def load_shape():

    shapecsv = get_path(f'{data_directory}/shape.csv')
   
    data = []
    if os.path.exists(shapecsv):
        with open(shapecsv, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                data.append(row[1])
                shape = [int(x) for x in data] #converts 'string' to integers in data
        return shape  
    else:
        shape = pd.DataFrame(data = {'Shape': [0]*51})   
        return shape 

# Function extracts keys from dictionary
def extract_keys(dict_, keys):
    return {k: dict_.get(k, None) for k in keys}

# This function terminates the audio connection
def refresh_audio_device_list():
    try:
        p = pyaudio.PyAudio()
        p.terminate()
        time.sleep(1)
        return
    except:
        return

# This function gets a list of audio device_list connected to the computer           
def get_device_list():
    refresh_audio_device_list()
    p = pyaudio.PyAudio()
    try:
        device_count = p.get_device_count()
        input_device_list = [
            (p.get_device_info_by_index(i)['name'], p.get_device_info_by_index(i)['index'])
            for i in range(device_count)
            if p.get_device_info_by_index(i)['maxInputChannels'] >= 1
        ]
        p.terminate()
        return input_device_list
    except:
        p.terminate()
        return [('no device', 99)]
     

# Returns maxInputChannels in an unordered list
def get_max_input_channels(device):
    p = pyaudio.PyAudio()
    channels = p.get_device_info_by_index(device)['maxInputChannels']
    return channels

# Function to open browser on localhost
def open_browser(port):
    webbrowser.open_new("http://localhost:{}".format(port))    
    return

def create_dummy_csv(filepath):
    with open(filepath, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        for i in range(0, 50):
            writer.writerow([i, 0])
 
# Function to automatically switch between positive and negative pulses
def detect_pulse_direction(samples):
    if max(samples) >= 3000:
        return 1
    if min(samples) <= -3000:
        return -1
    else:
        return 0

def get_path(filename):
    name, ext = os.path.splitext(filename)

    if platform.system() == "Darwin":
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(bundle_dir, f"{name}{ext}")
        return file if os.path.exists(file) else os.path.realpath(filename)
    else:
        return os.path.realpath(filename)

def restart_program():
    subprocess.Popen(['python', 'app.py'])
    return

def shutdown():
    print('Shutting down server...')
    os._exit(0)

def peakfinder(y_values, prominence, min_width):
    # y * bin to give higher value toweards the right
    y_bin = [y * i for i, y in enumerate(y_values)]
    # Find all peaks of prominence
    peaks, _ = find_peaks(y_bin, prominence=prominence, distance = 40)
    # Get the fwhm for all foundpeaks
    widths, _, _, _ = peak_widths(y_values, peaks, rel_height=0.5)
    # Filter out peaks where width >= min-width
    filtered_peaks = [p for i, p in enumerate(peaks) if widths[i] >= min_width * i]
    # Define array
    fwhm = []
    # Get widths of filtered_peaks
    for i in range(len(filtered_peaks)):
        w, _, _, _ = peak_widths(y_values, [filtered_peaks[i]], rel_height=0.5)
        w = np.round(w,1)
        fwhm.append(w[0])
    return filtered_peaks, fwhm

def get_gps_loc():
    # load data into array
    data = json.load(urlopen("https://ipinfo.io/json"))
    # extract lattitude
    lat = data['loc'].split(',')[0]
    # extract longitude
    lon = data['loc'].split(',')[1]
    return lat, lon

def gaussian_correl(data, sigma):
    # Initialize an empty list to hold the correlation values
    correl_values = []
    # Iterate over each index in the input data array
    for index in range(len(data)):
        # Compute the standard deviation of the Gaussian kernel
        std = math.sqrt(len(data))
        # Compute the range of indices to include in the Gaussian kernel
        x_min = -round(sigma * std)
        x_max = round(sigma * std)
        # Compute the Gaussian kernel values
        gauss_values = []
        for k in range(x_min, x_max):
            # Compute the Gaussian kernel value for the current index
            gauss_values.append(math.exp(-(k**2) / (2 * std**2)))
        # Compute the average of the Gaussian kernel values
        avg = sum(gauss_values) / (x_max - x_min) if (x_max - x_min) > 0 else 0
        # Compute the squared sum of the difference between the Gaussian kernel values and the average
        squared_sum = 0
        for value in gauss_values:
            squared_sum += (value - avg)**2
        # Compute the correlation value for the current index
        result_val = 0
        for k in range(x_min, x_max):
            # Check that the index is within bounds of the data array
            if index + k < 0 or index + k >= len(data):
                continue
            # Compute the contribution of the data at the current index and the Gaussian kernel value to the correlation value
            result_val += data[index + k] * (gauss_values[k - x_min] - avg) / squared_sum
        # Set the correlation value to the computed result value if it is positive, otherwise set it to zero
        value = result_val if result_val and result_val > 0 else 0
        # Append the correlation value to the list of correlation values
        correl_values.append(value)
    # Scale the correlation values based on the maximum value in the input data array
    scaling_factor = 0.8 * max(data) / max(correl_values)
    correl_values = [value * scaling_factor for value in correl_values]
    # Return the list of correlation values
    return correl_values

def stop_recording():

    # This function is an ugly botch but it works
    # To stop the while loop we first get max counts
    # then zeroise max counts
    # then put the original number back again

    # I think threading can be used to interrupt the loop, but will require some rewriting

    database = get_path(f'{data_directory}/.data.db')
    conn     = sql.connect(database)
    query1  = "SELECT max_counts FROM settings "
    c       = conn.cursor()
    c.execute(query1)
    conn.commit()
    max_counts = c.fetchall()[0][0]
    query2 = "UPDATE settings SET max_counts = 0 WHERE ID = 0;"
    c      = conn.cursor()
    c.execute(query2)
    conn.commit()
    time.sleep(3)
    # Wait three seconds and set max_counts back to what it was
    query3    = f"UPDATE settings SET max_counts = {max_counts} WHERE ID = 0;"
    c         = conn.cursor()
    c.execute(query3)
    conn.commit()
    return    

def export_csv(filename):
    # Get the path to the user's download folder
    download_folder = os.path.expanduser("~/Downloads")
    # Remove the ".json" extension from the filename
    base_filename = filename.rsplit(".", 1)[0]
    # Give output file a name
    output_file = f'{base_filename}.txt'
    # Load json file
    with open(f'{data_directory}/{filename}') as f:
        data = json.load(f)
    # Extract data from json file
    spectrum     = data["resultData"]["energySpectrum"]["spectrum"]
    coefficients = data["resultData"]["energySpectrum"]["energyCalibration"]["coefficients"]
    # Make sure coefficient[2] is not negative
    if coefficients[2] <= 0:
        coefficients[2] = 0
    # Open file in Download directory
    with open(os.path.join(download_folder, output_file), "w", newline="") as f:
        # Write to file
        writer = csv.writer(f)
        # Write heading row
        writer.writerow(["bin", "counts"])
        # Write each row
        for i, value in enumerate(spectrum):
            # Calculate energies
            e = round((i**coefficients[2] + i*coefficients[1]+coefficients[0]),2)
            writer.writerow([e, value])   
    return

def update_coeff(filename, coeff_1, coeff_2, coeff_3):
    with open(f'{data_directory}/{filename}.json') as f:
        data = json.load(f)

    coefficients = data["resultData"]["energySpectrum"]["energyCalibration"]["coefficients"]
    coefficients[0] = coeff_3
    coefficients[1] = coeff_2
    coefficients[2] = coeff_1

    with open(f'{data_directory}/{filename}.json', 'w') as f:
        json.dump(data, f, indent=4)

    return