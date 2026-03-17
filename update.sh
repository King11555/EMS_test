#!/bin/sh

# ------------------------- CONFIG -------------------------
REPO_ZIP_URL="https://github.com/King11555/EMS_test/archive/refs/heads/main.zip"
LOCAL_FOLDER="./EMS_test"
TMP_ZIP="repo.zip"
TMP_DIR="repo_tmp"

# ------------------------- DOWNLOAD -------------------------
echo "Downloading repository..."
wget -q -O "$TMP_ZIP" "$REPO_ZIP_URL" \
    && echo "✅ Downloaded $REPO_ZIP_URL" \
    || { echo "❌ Download failed!"; exit 1; }

# ------------------------- CLEAN OLD FILES -------------------------
echo "Cleaning old temporary files..."
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

# ------------------------- EXTRACT -------------------------
echo "Extracting repository..."
unzip -q "$TMP_ZIP" -d "$TMP_DIR" \
    && echo "✅ Extraction complete" \
    || { echo "❌ Extraction failed!"; rm -f "$TMP_ZIP"; exit 1; }

# ------------------------- DETECT EXTRACTED FOLDER -------------------------
EXTRACTED_FOLDER=$(find "$TMP_DIR" -maxdepth 1 -type d -name "EMS_test-*")
if [ -z "$EXTRACTED_FOLDER" ]; then
    echo "❌ Could not find extracted folder!"
    rm -rf "$TMP_DIR" "$TMP_ZIP"
    exit 1
fi

# ------------------------- OVERWRITE LOCAL FOLDER -------------------------
echo "Updating $LOCAL_FOLDER with latest files..."

# Ensure local folder exists
mkdir -p "$LOCAL_FOLDER"

# Remove old contents of LOCAL_FOLDER (but keep the folder itself)
rm -rf "$LOCAL_FOLDER"/* "$LOCAL_FOLDER"/.*

# Copy all files including hidden files from extracted folder
cp -r "$EXTRACTED_FOLDER"/. "$LOCAL_FOLDER"/

# ------------------------- CLEANUP -------------------------
rm -rf "$TMP_DIR" "$TMP_ZIP"

echo "✅ Update complete. '$LOCAL_FOLDER' now contains the latest version."