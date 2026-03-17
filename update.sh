#!/bin/sh

# ------------------------- CONFIG -------------------------
REPO_ZIP_URL="https://github.com/King11555/EMS_test/archive/refs/heads/main.zip"
LOCAL_FOLDER="./EMS_test"
TMP_ZIP="repo.zip"
TMP_DIR="repo_tmp"

# ------------------------- DOWNLOAD -------------------------
echo "Downloading repository..."
if wget -q -O "$TMP_ZIP" "$REPO_ZIP_URL"; then
    echo "✅ Downloaded $REPO_ZIP_URL"
else
    echo "❌ Download failed!"
    exit 1
fi

# ------------------------- CLEAN OLD FILES -------------------------
echo "Cleaning old files..."
rm -rf "$TMP_DIR"
# Do not delete LOCAL_FOLDER yet in case copy fails, safer to overwrite later

# ------------------------- EXTRACT -------------------------
echo "Extracting repository..."
mkdir -p "$TMP_DIR"
if unzip -q "$TMP_ZIP" -d "$TMP_DIR"; then
    echo "✅ Extraction complete"
else
    echo "❌ Extraction failed!"
    rm -f "$TMP_ZIP"
    exit 1
fi

# ------------------------- DETECT EXTRACTED FOLDER -------------------------
EXTRACTED_FOLDER=$(find "$TMP_DIR" -maxdepth 1 -type d -name "EMS_test-*")

if [ -z "$EXTRACTED_FOLDER" ]; then
    echo "❌ Could not find extracted folder!"
    rm -rf "$TMP_DIR" "$TMP_ZIP"
    exit 1
fi

# ------------------------- MOVE FILES -------------------------
echo "Updating $LOCAL_FOLDER with latest files..."
mkdir -p "$LOCAL_FOLDER"

# Copy all files including hidden ones from the extracted folder into your local folder
cp -r "$EXTRACTED_FOLDER"/. "$LOCAL_FOLDER"/

# ------------------------- CLEANUP -------------------------
rm -rf "$TMP_DIR" "$TMP_ZIP"

echo "✅ Update complete. '$LOCAL_FOLDER' now contains the latest version."