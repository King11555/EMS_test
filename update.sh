#!/bin/sh

# Folder to save/update files
LOCAL_FOLDER="./"

# Make sure folder exists
mkdir -p "$LOCAL_FOLDER"

# Update EMS_test.py
echo "Updating EMS_test.py ..."
wget -q -O "$LOCAL_FOLDER/EMS_test.py" "https://raw.githubusercontent.com/King11555/EMS_test/refs/heads/main/EMS_test.py"
if [ $? -eq 0 ]; then
    echo "✅ EMS_test.py updated successfully."
else
    echo "❌ Failed to update EMS_test.py."
fi

# Update config.yaml
echo "Updating config.yaml ..."
wget -q -O "$LOCAL_FOLDER/config.yaml" "https://raw.githubusercontent.com/King11555/EMS_test/refs/heads/main/config.yaml"
if [ $? -eq 0 ]; then
    echo "✅ config.yaml updated successfully."
else
    echo "❌ Failed to update config.yaml."
fi