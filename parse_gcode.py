import math
import argparse
from pathlib import Path

def read_gcode(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    return lines

gcode_path = 'CE3E3V2_xSM41_1.gcode'
gcode_output = 'cleaned.gcode'
gcode_lines = read_gcode(gcode_path)


def parse_layers(gcode_lines):
    layers = {}
    current_layer = None
    for line in gcode_lines:
        if line.startswith(';LAYER:'):
            current_layer = int(line.strip().split(':')[1])
            layers[current_layer] = []
        if current_layer is not None and (line.startswith('G0') or line.startswith('G1')):
            layers[current_layer].append(line.strip())
    return layers

layers = parse_layers(gcode_lines)

def calculate_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def calculate_time(distance, speed):
    return distance / speed

def extract_coordinates(command):
    coords = {'X': None, 'Y': None}
    parts = command.split()
    for part in parts:
        if part.startswith('X'):
            coords['X'] = float(part[1:])
        elif part.startswith('Y'):
            coords['Y'] = float(part[1:])
    return coords

def calculate_time(distance, speed):
    # Convert speed from mm/minute to mm/second
    speed /= 60
    return distance / speed

def process_layer(commands):
    time_total = 0
    last_coords = {'X': 0, 'Y': 0}
    for command in commands:
        if 'X' in command or 'Y' in command:
            coords = extract_coordinates(command)
            # Assuming a constant speed for simplicity; adjust as needed.
            speed = 1500  # mm/min, example speed
            if coords['X'] is None:
                coords['X'] = last_coords['X']
            if coords['Y'] is None:
                coords['Y'] = last_coords['Y']
            distance = calculate_distance(last_coords['X'], last_coords['Y'], coords['X'], coords['Y'])
            time_total += calculate_time(distance, speed)
            last_coords = coords
    return time_total

layer_times = {layer: process_layer(commands) for layer, commands in layers.items()}
def print_layer_times(layer_times):
    for layer, time in sorted(layer_times.items()):
        print(f"Layer {layer}: estimated {time:.2f} seconds")

def analyze_time_changes(layer_times, change_ratio = 0.2):
    previous_time = None
    for layer, time in sorted(layer_times.items()):
        if previous_time is not None:
            change = (time - previous_time) / previous_time
            if abs(change) > change_ratio:
                print(f"Significant change at layer {layer}: {change*100:.2f}%")
        previous_time = time

# analyze_time_changes(layer_times)


def smooth_layer_times_with_percentage(layer_times, change_ratio=0.2):
    n = len(layer_times)
    
    # Forward pass: Increase times if needed to not decrease more than 20% from previous
    for i in range(1, n):
        max_time = layer_times[i - 1] * (1 - change_ratio)
        if layer_times[i] < max_time:
            layer_times[i] = max_time
    
    # Backward pass: Increase times if needed to not decrease more than 20% from next
    for i in range(n - 2, -1, -1):
        max_time = layer_times[i + 1] * (1 - change_ratio)
        if layer_times[i] < max_time:
            layer_times[i] = max_time
    
    return layer_times

smoothed_times = smooth_layer_times_with_percentage(layer_times.copy())

def print_layer_times_comparison(original_times, smoothed_times):
    # Print table header
    print("{:<10} {:<15} {:<15} {:<15}".format('Layer', 'Original Value', 'Updated Value', 'Seconds to Add'))
    print("-" * 60)  # Print a separator line

    # Ensure layers are sorted by layer number (keys of the dictionary)
    sorted_original = sorted(original_times.items())
    sorted_smoothed = sorted(smoothed_times.items())

    # Print each layer's times and their deltas
    for (orig_layer, orig_time), (smooth_layer, smooth_time) in zip(sorted_original, sorted_smoothed):
        delta = smooth_time - orig_time
        print("{:<10} {:<15} {:<15} {:<15}".format(orig_layer, f"{orig_time:.2f}", f"{smooth_time:.2f}", f"{delta:.2f}"))


def update_gcode_with_dwell(gcode_lines, layer_times, target_times):
    updated_gcode = []
    current_layer = None

    for index, line in enumerate(gcode_lines):
        updated_gcode.append(line)
        if ";LAYER:" in line:
            layer_number = int(line.split(':')[1])  # Extracting layer number from the G-code line
            current_layer = layer_number
            if current_layer in layer_times and current_layer in target_times:  # Check if the layer number exists in dictionaries
                actual_time = layer_times[current_layer]
                target_time = target_times[current_layer]
                if actual_time < target_time:
                    dwell_time = target_time - actual_time
                    #dwell_command = f"G4 P{int(dwell_time * 1000)} ; Dwell for {dwell_time:.2f} seconds\n"
                    dwell_commands = insert_incremental_dwell(dwell_time, 10)
                    dwell_commands_str = ''.join(dwell_commands)
                    for cmd in dwell_commands:
                      updated_gcode.append(cmd)

    return updated_gcode

def insert_incremental_dwell(dwell_time, segment_length=30):
    # This function will return a list of dwell commands broken down into smaller segments
    commands = []
    full_segments = int(dwell_time // segment_length)
    remaining_time = dwell_time % segment_length

    for _ in range(full_segments):
        commands.append(f"G4 P{segment_length * 1000} ; Dwell for {segment_length} seconds\n")
    
    if remaining_time > 0:
        commands.append(f"G4 P{int(remaining_time * 1000)} ; Dwell for {remaining_time:.2f} seconds\n")
    
    return commands



def main():
    parser = argparse.ArgumentParser(description="G-code Layer Time Adjustment Tool")
    parser.add_argument("input_file", type=str, help="Path to the input G-code file")
    parser.add_argument("--output_file", type=str, default="", help="Path to the output G-code file (required for clean mode)")
    parser.add_argument("--variance", type=float, default=20.0, help="Allowable percentage variance between layers")
    parser.add_argument("--mode", type=str, choices=["analyze", "clean"], required=True, help="Operational mode: analyze or clean")

    args = parser.parse_args()

    gcode_lines = read_gcode(args.input_file)
    layers = parse_layers(gcode_lines)  # Assuming this function parses layers and extracts commands
    layer_times = {layer: process_layer(commands) for layer, commands in layers.items()}
    
    if args.mode == "analyze":
        # Print problem layers and proposed changes
        print_layer_times_comparison(layer_times, smooth_layer_times_with_percentage(layer_times.copy(), args.variance / 100.0))
    elif args.mode == "clean":
        if args.output_file:
            # Generate updated G-code with dwell times
            target_times = smooth_layer_times_with_percentage(layer_times.copy(), args.variance / 100.0)
            updated_gcode = update_gcode_with_dwell(gcode_lines, layer_times, target_times)
            with open(args.output_file, 'w') as f:
                f.writelines(updated_gcode)
            print(f"Updated G-code has been saved to {args.output_file}")
            print(f"You can compare the difference in vscode with code --diff {args.input_file} {args.output_file}")
        else:
            print("Output file path is required for clean mode.")

if __name__ == "__main__":
    main()
