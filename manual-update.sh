#!/bin/bash
#===============================================================================
#          FILE: manual-update.sh
#
#         USAGE: curl -sSL http://109.110.185.70/api/manual-update | sudo bash
#
#   DESCRIPTION: Manual update script for OLT Manager
#                Use this if auto-update fails
#
#===============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LICENSE_SERVER="http://109.110.185.70"

print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

# Detect install directory
if [[ -d "/opt/olt-manager/backend" ]]; then
    INSTALL_DIR="/opt/olt-manager"
elif [[ -d "/root/olt-manager/backend" ]]; then
    INSTALL_DIR="/root/olt-manager"
else
    print_error "OLT Manager installation not found!"
    exit 1
fi

BACKEND_DIR="$INSTALL_DIR/backend"

print_status "Detected installation at: $INSTALL_DIR"

# Get current version
CURRENT_VERSION="unknown"
if [[ -f "$BACKEND_DIR/VERSION" ]]; then
    CURRENT_VERSION=$(cat "$BACKEND_DIR/VERSION")
fi
print_status "Current version: $CURRENT_VERSION"

# Get latest version info
print_status "Checking for updates..."
VERSION_INFO=$(curl -s "$LICENSE_SERVER/api/latest-version" 2>/dev/null)

if echo "$VERSION_INFO" | grep -q '"available":true'; then
    LATEST_VERSION=$(echo "$VERSION_INFO" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    print_status "Latest version: $LATEST_VERSION"
else
    print_error "No updates available or could not connect to license server"
    exit 1
fi

# Download update
print_status "Downloading update package..."
PACKAGE_FILE="/tmp/olt-update-${LATEST_VERSION}.tar.gz"
curl -s -o "$PACKAGE_FILE" "$LICENSE_SERVER/api/download-update/$LATEST_VERSION"

if [[ ! -f "$PACKAGE_FILE" ]] || [[ ! -s "$PACKAGE_FILE" ]]; then
    print_error "Failed to download update package"
    exit 1
fi

print_success "Downloaded update package"

# Create backup
print_status "Creating backup..."
BACKUP_DIR="/tmp/olt-manager-backup-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r "$BACKEND_DIR" "$BACKUP_DIR/"
print_success "Backup created at $BACKUP_DIR"

# Extract update
print_status "Extracting update..."
EXTRACT_DIR="/tmp/olt-manager-update-extract"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$PACKAGE_FILE" -C "$EXTRACT_DIR"

# Apply backend update
print_status "Applying backend update..."
if [[ -d "$EXTRACT_DIR/backend" ]]; then
    cd "$EXTRACT_DIR/backend"
    for item in *; do
        # Skip directories that shouldn't be overwritten
        if [[ "$item" == "venv" ]] || [[ "$item" == "__pycache__" ]] || [[ "$item" == "uploads" ]]; then
            continue
        fi
        # Skip database files (NEVER overwrite customer data!)
        if [[ "$item" == *.db ]] || [[ "$item" == *.sqlite ]] || [[ "$item" == *.sqlite3 ]]; then
            print_status "Skipping database file: $item"
            continue
        fi
        cp -r "$item" "$BACKEND_DIR/"
    done
fi

# Apply frontend update
print_status "Applying frontend update..."
if [[ -d "$EXTRACT_DIR/frontend/build" ]]; then
    # Copy to both possible nginx directories
    for nginx_dir in /var/www/olt-manager /var/www/html; do
        if [[ -d "$nginx_dir" ]]; then
            cp -r "$EXTRACT_DIR/frontend/build/"* "$nginx_dir/"
            print_success "Updated frontend at $nginx_dir"
        fi
    done
fi

# Update version file
echo "$LATEST_VERSION" > "$BACKEND_DIR/VERSION"
print_success "Updated version to $LATEST_VERSION"

# Restart service
print_status "Restarting service..."
if systemctl is-active --quiet olt-backend; then
    systemctl restart olt-backend
    SERVICE_NAME="olt-backend"
elif systemctl is-active --quiet olt-manager; then
    systemctl restart olt-manager
    SERVICE_NAME="olt-manager"
else
    # Manual restart
    print_status "No systemd service found, trying manual restart..."
    pkill -f "uvicorn main:app" 2>/dev/null || true
    sleep 2
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup python -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/olt-manager.log 2>&1 &
    SERVICE_NAME="manual"
fi

sleep 3

# Verify
print_status "Verifying update..."
if curl -s http://localhost:8000/api/settings > /dev/null 2>&1; then
    print_success "Update completed successfully!"
    echo ""
    echo -e "${GREEN}OLT Manager updated from $CURRENT_VERSION to $LATEST_VERSION${NC}"
    echo ""
else
    print_error "Service failed to start after update"
    print_status "Check logs: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# Cleanup
rm -rf "$EXTRACT_DIR"
rm -f "$PACKAGE_FILE"

print_success "Cleanup completed"
