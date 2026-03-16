#!/bin/sh

# ----------------------------
# Configuration
# ----------------------------

# Folder where files will be saved/updated
LOCAL_FOLDER="./"

# List of files: filename and raw GitHub URL
FILES_TO_UPDATE="
EMS_test.py https://raw.githubusercontent.com/King11555/EMS_test/refs/heads/main/EMS_test.py
config.yaml https://raw.githubusercontent.com/King11555/EMS_test/refs/heads/main/config.yaml
"

# ----------------------------
# Update function
# ----------------------------
mkdir -p "$LOCAL_FOLDER"

for entry in $FILES_TO_UPDATE; do
    # Split entry into filename and URL
    FILE=$(echo $entry | awk '{print $1}')
    URL=$(echo $entry | awk '{print $2}')
    
    echo "Updating $FILE from $URL ..."
    wget -q -O "$LOCAL_FOLDER/$FILE" "$URL"
    if [ $? -eq 0 ]; then
        echo "✅ $FILE updated successfully."
    else
        echo "❌ Failed to update $FILE."
    fi
done