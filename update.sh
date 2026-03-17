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
rm -rf "$LOCAL_FOLDER"

# ------------------------- EXTRACT -------------------------
echo "Extracting repository..."
mkdir -p "$TMP_DIR"
if unzip -q "$TMP_ZIP" -d "$TMP_DIR"; then
    echo "✅ Extracted ZIP"
else
    echo "❌ Extraction failed!"
    rm -f "$TMP_ZIP"
    exit 1
fi

# ------------------------- MOVE FILES -------------------------
# Detect extracted folder (GitHub ZIP always names it <repo>-<branch>)
EXTRACTED_FOLDER=$(find "$TMP_DIR" -maxdepth 1 -type d -name "EMS_test-*")

if [ -z "$EXTRACTED_FOLDER" ]; then
    echo "❌ Could not find extracted folder!"
    rm -rf "$TMP_DIR" "$TMP_ZIP"
    exit 1
fi

echo "Moving files to $LOCAL_FOLDER..."
mkdir -p "$LOCAL_FOLDER"

# Move all files including hidden files
cp -r "$EXTRACTED_FOLDER"/. "$LOCAL_FOLDER"/

# ------------------------- CLEANUP -------------------------
rm -rf "$TMP_DIR" "$TMP_ZIP"

echo "✅ Update complete. Local folder '$LOCAL_FOLDER' now contains the latest version."