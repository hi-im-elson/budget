#!/bin/bash

# Source folder to zip
SOURCE_FOLDER="/Users/elson/repos/budget/pipeline"

# Name of the zip file (uses folder name)
FOLDER_NAME=$(basename "$SOURCE_FOLDER")
ZIP_FILE="$HOME/Downloads/${FOLDER_NAME}.zip"

# Create the zip archive
zip -r "$ZIP_FILE" "$SOURCE_FOLDER"

echo "Archive created: $ZIP_FILE"
