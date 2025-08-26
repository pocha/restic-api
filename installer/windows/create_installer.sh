#!/bin/bash

# Clean installer creation script for Windows
# This script copies fresh files, creates the installer zip, and cleans up

set -e

echo "🔧 Creating Windows installer..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALLER_DIR="$SCRIPT_DIR"
BINARIES_DIR="$PROJECT_ROOT/binaries"

echo "📁 Project root: $PROJECT_ROOT"
echo "📁 Installer dir: $INSTALLER_DIR"
echo "📁 Binaries dir: $BINARIES_DIR"

# Create binaries directory if it doesn't exist
mkdir -p "$BINARIES_DIR"

# List of files to copy from project root
FILES_TO_COPY=(
    "app.py"
    "requirements.txt"
    "restic-installer-scripts"
)

# Clean up any existing copied files first
echo "🧹 Cleaning up any existing copied files..."
for file in "${FILES_TO_COPY[@]}"; do
    if [ -e "$INSTALLER_DIR/$file" ]; then
        rm -rf "$INSTALLER_DIR/$file"
        echo "   Removed: $file"
    fi
done

# Copy fresh files from project root
echo "📋 Copying fresh files from project root..."
for file in "${FILES_TO_COPY[@]}"; do
    if [ -e "$PROJECT_ROOT/$file" ]; then
        cp -r "$PROJECT_ROOT/$file" "$INSTALLER_DIR/"
        echo "   Copied: $file"
    else
        echo "   ⚠️  Warning: $file not found in project root"
    fi
done

# Copy e2e_test.py (it should be fresh from project root)
if [ -e "$PROJECT_ROOT/e2e_test.py" ]; then
    cp "$PROJECT_ROOT/e2e_test.py" "$INSTALLER_DIR/"
    echo "   Copied: e2e_test.py"
fi

# Create the installer zip
echo "📦 Creating installer zip..."
cd "$INSTALLER_DIR"
zip -r "$BINARIES_DIR/restic-api-windows-installer.zip" . \
    -x "create_installer.sh" \
    -x "test_data/*" \
    -x ".git/*" \
    -x "__pycache__/*"

echo "✅ Installer created: $BINARIES_DIR/restic-api-windows-installer.zip"

# Clean up copied files
echo "🧹 Cleaning up copied files..."
for file in "${FILES_TO_COPY[@]}"; do
    if [ -e "$INSTALLER_DIR/$file" ]; then
        rm -rf "$INSTALLER_DIR/$file"
        echo "   Removed: $file"
    fi
done

# Remove copied e2e_test.py if it was copied from project root
if [ -e "$PROJECT_ROOT/e2e_test.py" ] && [ -e "$INSTALLER_DIR/e2e_test.py" ]; then
    # Only remove if they are the same (to avoid removing a customized version)
    if cmp -s "$PROJECT_ROOT/e2e_test.py" "$INSTALLER_DIR/e2e_test.py"; then
        rm "$INSTALLER_DIR/e2e_test.py"
        echo "   Removed: e2e_test.py (copy)"
    fi
fi

echo "🎉 Windows installer creation complete!"
echo "📍 Location: $BINARIES_DIR/restic-api-windows-installer.zip"

# Show installer contents
echo ""
echo "📋 Installer contents:"
unzip -l "$BINARIES_DIR/restic-api-windows-installer.zip"
