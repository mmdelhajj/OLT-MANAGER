#!/bin/bash
# ============================================
# OLT Manager - Manual Update Script
# For customer servers with compiled binaries
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

LICENSE_SERVER="https://lic.proxpanel.com"

echo -e "${YELLOW}========================================"
echo "  OLT Manager - Manual Update"
echo "========================================${NC}"

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root${NC}"
    exit 1
fi

# Get license key
LICENSE_KEY=""
if [ -f "/etc/olt-manager/license.key" ]; then
    LICENSE_KEY=$(cat /etc/olt-manager/license.key)
fi

if [ -z "$LICENSE_KEY" ]; then
    echo -e "${RED}Error: No license key found${NC}"
    exit 1
fi

# Get hardware ID
HARDWARE_ID=""
if [ -f "/etc/olt-manager/hardware.id" ]; then
    HARDWARE_ID=$(cat /etc/olt-manager/hardware.id)
fi

if [ -z "$HARDWARE_ID" ]; then
    echo -e "${RED}Error: No hardware ID found${NC}"
    exit 1
fi

echo -e "${GREEN}License Key: $LICENSE_KEY${NC}"
echo -e "${GREEN}Hardware ID: $HARDWARE_ID${NC}"

# Check for updates
echo ""
echo -e "${YELLOW}Checking for updates...${NC}"
UPDATE_INFO=$(curl -s -X POST "$LICENSE_SERVER/api/validate" \
    -H "Content-Type: application/json" \
    -d "{\"license_key\": \"$LICENSE_KEY\", \"hardware_id\": \"$HARDWARE_ID\", \"product\": \"olt-manager\", \"version\": \"0.0.0\"}")

if echo "$UPDATE_INFO" | grep -q '"error"'; then
    echo -e "${RED}Error checking updates: $(echo "$UPDATE_INFO" | grep -o '"error":"[^"]*"')${NC}"
    exit 1
fi

LATEST_VERSION=$(echo "$UPDATE_INFO" | grep -o '"latest_version":"[^"]*"' | cut -d'"' -f4)
CURRENT_VERSION=$(cat /opt/olt-manager/VERSION 2>/dev/null | head -1 || echo "unknown")

echo -e "Current version: ${YELLOW}$CURRENT_VERSION${NC}"
echo -e "Latest version:  ${GREEN}$LATEST_VERSION${NC}"

if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
    echo -e "${GREEN}You are running the latest version!${NC}"
    exit 0
fi

# Download update
echo ""
echo -e "${YELLOW}Downloading update v$LATEST_VERSION...${NC}"

UPDATE_DIR="/tmp/olt-manager-update-$$"
mkdir -p "$UPDATE_DIR"

DOWNLOAD_RESPONSE=$(curl -s -X POST "$LICENSE_SERVER/api/download-update" \
    -H "Content-Type: application/json" \
    -d "{\"license_key\": \"$LICENSE_KEY\", \"hardware_id\": \"$HARDWARE_ID\"}" \
    -o "$UPDATE_DIR/update.tar.gz" \
    -w "%{http_code}")

if [ "$DOWNLOAD_RESPONSE" != "200" ]; then
    echo -e "${RED}Error downloading update (HTTP $DOWNLOAD_RESPONSE)${NC}"
    rm -rf "$UPDATE_DIR"
    exit 1
fi

echo -e "${GREEN}Download complete${NC}"

# Extract update
echo ""
echo -e "${YELLOW}Extracting update...${NC}"
cd "$UPDATE_DIR"
tar -xzf update.tar.gz

# Apply update
echo ""
echo -e "${YELLOW}Applying update...${NC}"

# Check for install script in package
if [ -f "$UPDATE_DIR/install.sh" ]; then
    echo "Using package install script..."
    chmod +x "$UPDATE_DIR/install.sh"
    "$UPDATE_DIR/install.sh" "$UPDATE_DIR" "$LATEST_VERSION"
else
    # Manual install
    echo "Manual installation..."

    # Update frontend
    if [ -d "$UPDATE_DIR/frontend/build" ]; then
        echo "Updating frontend..."
        if [ -d "/var/www/olt-manager" ]; then
            cp -r "$UPDATE_DIR/frontend/build"/* /var/www/olt-manager/
        elif [ -d "/var/www/html" ]; then
            cp -r "$UPDATE_DIR/frontend/build"/* /var/www/html/
        fi
    fi

    # Update version
    echo "$LATEST_VERSION" > /opt/olt-manager/VERSION
fi

# Restart service
echo ""
echo -e "${YELLOW}Restarting service...${NC}"
if systemctl is-active --quiet olt-manager; then
    systemctl restart olt-manager
elif systemctl is-active --quiet olt-backend; then
    systemctl restart olt-backend
fi

# Cleanup
rm -rf "$UPDATE_DIR"

# Verify
sleep 2
NEW_VERSION=$(cat /opt/olt-manager/VERSION 2>/dev/null | head -1)

echo ""
echo -e "${GREEN}========================================"
echo "  Update Complete!"
echo "========================================"
echo "  New version: $NEW_VERSION"
echo "========================================${NC}"
