#!/bin/sh

REPO_ZIP_URL="https://github.com/King11555/EMS_test/archive/refs/heads/main.zip"
TMP_ZIP="../repo.zip"
TMP_DIR="../repo_tmp"
LOCAL_FOLDER="."

echo "Downloading repository..."
wget -q -O "$TMP_ZIP" "$REPO_ZIP_URL" \
    && echo "✅ Downloaded" \
    || { echo "❌ Download failed!"; exit 1; }

echo "Cleaning old temporary files..."
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

echo "Extracting repository..."
unzip -q "$TMP_ZIP" -d "$TMP_DIR" \
    && echo "✅ Extracted" \
    || { echo "❌ Extraction failed!"; rm -f "$TMP_ZIP"; exit 1; }

EXTRACTED_FOLDER=$(find "$TMP_DIR" -maxdepth 1 -type d -name "EMS_test-*")
if [ -z "$EXTRACTED_FOLDER" ]; then
    echo "❌ Could not find extracted folder!"
    rm -rf "$TMP_DIR" "$TMP_ZIP"
    exit 1
fi

echo "Overwriting current folder with latest files..."
# Copy everything from extracted folder into current folder, including hidden files
cp -r "$EXTRACTED_FOLDER"/. "$LOCAL_FOLDER"/

echo "Cleaning up..."
rm -rf "$TMP_DIR" "$TMP_ZIP"

echo "✅ Update complete. Current folder now has latest files."