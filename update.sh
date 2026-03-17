#!/bin/sh

REPO_ZIP_URL="https://github.com/King11555/EMS_test/archive/refs/heads/main.zip"
LOCAL_FOLDER="./EMS_test"
TMP_ZIP="repo.zip"
TMP_DIR="repo_tmp"

echo "Downloading repository..."
wget -q -O "$TMP_ZIP" "$REPO_ZIP_URL" \
    && echo "✅ Downloaded." \
    || { echo "❌ Download failed."; exit 1; }

echo "Cleaning old files..."
rm -rf "$TMP_DIR"
rm -rf "$LOCAL_FOLDER"

echo "Extracting..."
mkdir -p "$TMP_DIR"
unzip -q "$TMP_ZIP" -d "$TMP_DIR" \
    && echo "✅ Extracted." \
    || { echo "❌ Extraction failed."; exit 1; }

echo "Moving files..."
mv "$TMP_DIR"/EMS_test-main "$LOCAL_FOLDER"

echo "Cleaning up..."
rm -rf "$TMP_ZIP" "$TMP_DIR"

echo "✅ Update complete."