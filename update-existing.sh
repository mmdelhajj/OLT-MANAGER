#!/bin/bash

#===============================================================================
#
#          FILE: update-existing.sh
#
#   DESCRIPTION: Update existing OLT Manager installation with latest fixes
#
#===============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         OLT Manager Pro - Update Existing Installation       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Error: Run as root (sudo)${NC}"
    exit 1
fi

# Check if OLT Manager is installed
if [ ! -d "/opt/olt-manager" ]; then
    echo -e "${RED}Error: OLT Manager not found at /opt/olt-manager${NC}"
    echo "Please run fresh install first."
    exit 1
fi

echo -e "${YELLOW}[1/5]${NC} Stopping backend service..."
systemctl stop olt-backend 2>/dev/null || systemctl stop olt-manager 2>/dev/null || true
sleep 2

echo -e "${YELLOW}[2/5]${NC} Backing up current installation..."
BACKUP_DIR="/opt/olt-manager-backup-$(date +%Y%m%d-%H%M%S)"
cp -r /opt/olt-manager "$BACKUP_DIR"
echo "  Backup saved to: $BACKUP_DIR"

echo -e "${YELLOW}[3/5]${NC} Updating backend (main.py)..."
cp /root/olt-manager/backend/main.py /opt/olt-manager/main.py 2>/dev/null || \
cp /root/olt-manager/backend/main.py /root/olt-manager/backend/main.py

echo -e "${YELLOW}[4/5]${NC} Updating frontend..."
rm -rf /var/www/html/*
cp -r /root/olt-manager/frontend/build/* /var/www/html/
rm -rf /opt/olt-manager/static/*
cp -r /root/olt-manager/frontend/build/* /opt/olt-manager/static/

echo -e "${YELLOW}[5/5]${NC} Restarting services..."
systemctl start olt-backend 2>/dev/null || systemctl start olt-manager 2>/dev/null || true
systemctl reload nginx

sleep 3

# Check if service is running
if systemctl is-active --quiet olt-backend 2>/dev/null || systemctl is-active --quiet olt-manager 2>/dev/null; then
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    UPDATE SUCCESSFUL!                        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${GREEN}✓${NC} Backend updated"
    echo -e "  ${GREEN}✓${NC} Frontend updated"
    echo -e "  ${GREEN}✓${NC} Services restarted"
    echo ""
    echo -e "  ${YELLOW}Note:${NC} Clear browser cache (Ctrl+Shift+R) to see changes"
    echo ""
else
    echo -e "${RED}Warning: Service may not have started. Check with: systemctl status olt-backend${NC}"
fi
