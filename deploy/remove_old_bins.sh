#!/bin/bash

# Check if the correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <directory> <number_of_newest_files_to_keep>"
    exit 1
fi

# Directory containing the firmware files
DIR="$1"

# Number of newest files to keep
NUM_FILES_TO_KEEP="$2"

# Function to sort firmware files
bin_sort() {
    local bin="$1"
    if [[ "$bin" == latest* ]]; then
        echo "100.0.0.0"
    else
        version="${bin%.bin}"
        fw_beta=(${version//-/ })
        fw="${fw_beta[0]}"
        beta=1000
        if [[ ${#fw_beta[@]} -gt 1 ]]; then
            beta="${fw_beta[1]#b}"
        fi
        IFS='.' read -r -a major_minor_patch <<< "$fw"
        major="${major_minor_patch[0]}"
        minor="${major_minor_patch[1]:-0}"
        patch="${major_minor_patch[2]:-0}"
        echo "$major.$minor.$patch.$beta"
    fi
}

echo "Starting cleanup in directory: $DIR"
echo "Keeping the newest $NUM_FILES_TO_KEEP firmware files"
echo "-----------------------------------------"

# Get list of firmware files
firmware_files=$(ls "$DIR" | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?(-b[0-9]+)?\.bin$')
echo "Firmware files found:"
printf "%s\n" "${firmware_files[@]}"
echo "-----------------------------------------"

# Sort the firmware files
sorted_files=($(echo "$firmware_files" | while read -r file; do echo "$(bin_sort "$file") $file"; done | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | awk '{print $2}'))

echo "Sorted files:"
printf "%s\n" "${sorted_files[@]}"
echo "-----------------------------------------"

# Get the newest files to keep
newest_files=($(printf "%s\n" "${sorted_files[@]}" | tail -n "$NUM_FILES_TO_KEEP"))

echo "Newest files to keep:"
printf "%s\n" "${newest_files[@]}"
echo "-----------------------------------------"

# Delete all files except the newest files
for file in "${sorted_files[@]}"; do
    if ! printf "%s\n" "${newest_files[@]}" | grep -q "$file"; then
        echo "Deleting file: $file"
        rm "$DIR/$file"
    else
        echo "Keeping file: $file"
    fi
done

echo "Cleanup completed."
