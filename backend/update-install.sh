#!/bin/bash
# OLT Manager Update Install Script
# This script is included in update packages and handles the installation
# Works for both compiled binary and source installations

set -e

EXTRACT_DIR="$1"
NEW_VERSION="$2"

if [ -z "$EXTRACT_DIR" ] || [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <extract_dir> <new_version>"
    exit 1
fi

echo "Installing OLT Manager update v${NEW_VERSION}..."

# Detect installation type
if [ -f "/opt/olt-manager/olt-manager" ]; then
    # Compiled binary installation
    INSTALL_TYPE="compiled"
    INSTALL_DIR="/opt/olt-manager"
    VERSION_FILE="/opt/olt-manager/VERSION"
    echo "Detected: Compiled binary installation"
elif [ -d "/opt/olt-manager/backend" ]; then
    # Source installation at /opt
    INSTALL_TYPE="source"
    INSTALL_DIR="/opt/olt-manager"
    BACKEND_DIR="/opt/olt-manager/backend"
    VERSION_FILE="/opt/olt-manager/backend/VERSION"
    echo "Detected: Source installation at /opt"
elif [ -d "/root/olt-manager/backend" ]; then
    # Development installation
    INSTALL_TYPE="source"
    INSTALL_DIR="/root/olt-manager"
    BACKEND_DIR="/root/olt-manager/backend"
    VERSION_FILE="/root/olt-manager/backend/VERSION"
    echo "Detected: Development installation"
else
    echo "ERROR: Could not detect installation type"
    exit 1
fi

# Detect frontend directory
if [ -d "/var/www/olt-manager" ]; then
    FRONTEND_DIR="/var/www/olt-manager"
elif [ -d "/var/www/html" ]; then
    FRONTEND_DIR="/var/www/html"
else
    echo "WARNING: No frontend directory found"
    FRONTEND_DIR=""
fi

# Create backup
echo "Creating backup..."
BACKUP_DIR="/tmp/olt-manager-backup-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ "$INSTALL_TYPE" = "source" ] && [ -d "$BACKEND_DIR" ]; then
    cp -r "$BACKEND_DIR" "$BACKUP_DIR/backend" 2>/dev/null || true
fi

if [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then
    cp -r "$FRONTEND_DIR" "$BACKUP_DIR/frontend" 2>/dev/null || true
fi

echo "Backup created at $BACKUP_DIR"

# Update backend (source installations only)
if [ "$INSTALL_TYPE" = "source" ] && [ -d "$EXTRACT_DIR/backend" ]; then
    echo "Updating backend..."
    for item in "$EXTRACT_DIR/backend"/*; do
        name=$(basename "$item")
        # Skip venv and __pycache__
        if [ "$name" != "venv" ] && [ "$name" != "__pycache__" ] && [ "$name" != "data" ]; then
            if [ -d "$item" ]; then
                rm -rf "$BACKEND_DIR/$name" 2>/dev/null || true
                cp -r "$item" "$BACKEND_DIR/$name"
            else
                cp "$item" "$BACKEND_DIR/$name"
            fi
        fi
    done
    echo "Backend updated"
elif [ "$INSTALL_TYPE" = "compiled" ]; then
    echo "Skipping backend update (compiled binary - update binary separately if needed)"
fi

# Update frontend
if [ -n "$FRONTEND_DIR" ] && [ -d "$EXTRACT_DIR/frontend/build" ]; then
    echo "Updating frontend..."
    for item in "$EXTRACT_DIR/frontend/build"/*; do
        name=$(basename "$item")
        if [ -d "$item" ]; then
            rm -rf "$FRONTEND_DIR/$name" 2>/dev/null || true
            cp -r "$item" "$FRONTEND_DIR/$name"
        else
            cp "$item" "$FRONTEND_DIR/$name"
        fi
    done
    echo "Frontend updated"
fi

# Update version file
echo "Updating version to $NEW_VERSION..."
echo "$NEW_VERSION" > "$VERSION_FILE"

echo "Update v${NEW_VERSION} installed successfully!"
echo "Service will be restarted..."

# Return success
exit 0
