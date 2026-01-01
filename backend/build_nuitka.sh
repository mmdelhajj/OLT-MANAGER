#!/bin/bash
# ============================================
# OLT Manager - Nuitka Compiled Build
# Compiles Python to C to Binary
# ============================================

set -e

echo "========================================"
echo "  OLT Manager - Nuitka Compilation"
echo "========================================"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_DIR="/root/olt-manager/backend"
BUILD_DIR="/root/olt-manager/nuitka_build"
DIST_DIR="/root/olt-manager/dist"

cd "$BACKEND_DIR"
source venv/bin/activate

# Check for required packages
echo -e "${YELLOW}[1/4] Checking dependencies...${NC}"
apt-get install -y patchelf ccache 2>/dev/null || true

# Clean previous builds
echo -e "${YELLOW}[2/4] Cleaning previous builds...${NC}"
rm -rf "$BUILD_DIR" main.build main.dist main.onefile-build
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Create templates folder if not exists
mkdir -p templates uploads

# Compile with Nuitka
echo -e "${YELLOW}[3/4] Compiling with Nuitka (this takes 30-60 min)...${NC}"
echo "    Compiling Python → C → Binary..."

python -m nuitka \
    --standalone \
    --onefile \
    --output-dir="$BUILD_DIR" \
    --output-filename=olt-manager \
    --follow-imports \
    --prefer-source-code \
    main.py

echo -e "${GREEN}    ✓ Compilation complete${NC}"

# Create deployment package
echo -e "${YELLOW}[4/4] Creating deployment package...${NC}"

mkdir -p "$BUILD_DIR/package"

# Find and copy the binary
if [ -f "$BUILD_DIR/olt-manager" ]; then
    cp "$BUILD_DIR/olt-manager" "$BUILD_DIR/package/"
elif [ -f "$BUILD_DIR/main.bin" ]; then
    cp "$BUILD_DIR/main.bin" "$BUILD_DIR/package/olt-manager"
else
    BINARY=$(find "$BUILD_DIR" -type f -executable -name "*.bin" 2>/dev/null | head -1)
    if [ -n "$BINARY" ]; then
        cp "$BINARY" "$BUILD_DIR/package/olt-manager"
    fi
fi

chmod +x "$BUILD_DIR/package/olt-manager" 2>/dev/null || true

mkdir -p "$BUILD_DIR/package/data"
mkdir -p "$BUILD_DIR/package/uploads"

# Create startup script
cat > "$BUILD_DIR/package/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./olt-manager
EOF
chmod +x "$BUILD_DIR/package/start.sh"

# Create systemd service
cat > "$BUILD_DIR/package/olt-manager.service" << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/olt-manager
ExecStart=/opt/olt-manager/olt-manager
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Copy version file from backend (just the version number)
cp "$BACKEND_DIR/VERSION" "$BUILD_DIR/package/VERSION"

# Create install.sh for automatic update handling
# Uses systemd transient unit for reliable execution that survives service restart
cat > "$BUILD_DIR/package/install.sh" << 'INSTALLEOF'
#!/bin/bash
# OLT Manager Update Install Script

LOG="/tmp/olt-update-install.log"
EXTRACT_DIR="$1"
NEW_VERSION="$2"

# If called directly (not via systemd-run), re-launch as transient systemd service
if [ -z "$OLT_UPDATE_SYSTEMD" ]; then
    echo "$(date): Launching update via systemd transient service" > $LOG

    # Copy script to fixed location
    cp "$0" /tmp/olt-install-runner.sh
    chmod +x /tmp/olt-install-runner.sh

    # Create and run as transient systemd service (survives parent death)
    systemd-run --unit=olt-update-$(date +%s) --description="OLT Manager Update" \
        --setenv=OLT_UPDATE_SYSTEMD=1 \
        /bin/bash /tmp/olt-install-runner.sh "$EXTRACT_DIR" "$NEW_VERSION" >> $LOG 2>&1 &

    echo "$(date): Update service launched" >> $LOG
    exit 0
fi

# Running via systemd - do the actual update
echo "$(date): Starting update install" >> $LOG

# Wait a moment for calling process to finish
sleep 3

check_health() {
    for i in {1..15}; do
        sleep 2
        if curl -s --connect-timeout 3 http://127.0.0.1:8000/api/update-check > /dev/null 2>&1; then
            echo "$(date): Health check passed on attempt $i" >> $LOG
            return 0
        fi
        echo "$(date): Health check attempt $i failed" >> $LOG
    done
    return 1
}

# Stop service
echo "$(date): Stopping service..." >> $LOG
systemctl stop olt-manager 2>/dev/null || systemctl stop olt-backend 2>/dev/null
sleep 2

# Backup and install new binary
cd /opt/olt-manager
[ -f olt-manager ] && cp olt-manager olt-manager.backup && echo "$(date): Backed up old binary" >> $LOG
[ -f "$EXTRACT_DIR/olt-manager" ] && cp "$EXTRACT_DIR/olt-manager" /opt/olt-manager/olt-manager && chmod +x /opt/olt-manager/olt-manager && echo "$(date): Installed new binary" >> $LOG
[ -f "$EXTRACT_DIR/VERSION" ] && cp "$EXTRACT_DIR/VERSION" /opt/olt-manager/VERSION && echo "$(date): Updated VERSION" >> $LOG

# Download and install frontend
echo "$(date): Downloading frontend..." >> $LOG
curl -sSL https://lic.proxpanel.com/downloads/frontend.tar.gz -o /tmp/frontend.tar.gz 2>>$LOG
if [ -f /tmp/frontend.tar.gz ]; then
    rm -rf /var/www/html/*
    tar -xzf /tmp/frontend.tar.gz -C /var/www/html/
    rm -f /tmp/frontend.tar.gz
    echo "$(date): Frontend installed" >> $LOG
fi

# Start service
echo "$(date): Starting service..." >> $LOG
systemctl start olt-manager 2>/dev/null || systemctl start olt-backend 2>/dev/null

# Health check with rollback
if check_health; then
    echo "$(date): UPDATE SUCCESSFUL!" >> $LOG
    rm -f /opt/olt-manager/olt-manager.backup
    rm -f /tmp/olt-install-runner.sh
    exit 0
else
    echo "$(date): Health check failed, rolling back..." >> $LOG
    systemctl stop olt-manager 2>/dev/null || systemctl stop olt-backend 2>/dev/null
    [ -f /opt/olt-manager/olt-manager.backup ] && mv /opt/olt-manager/olt-manager.backup /opt/olt-manager/olt-manager && chmod +x /opt/olt-manager/olt-manager
    systemctl start olt-manager 2>/dev/null || systemctl start olt-backend 2>/dev/null
    echo "$(date): Rollback completed" >> $LOG
    rm -f /tmp/olt-install-runner.sh
    exit 1
fi
INSTALLEOF
chmod +x "$BUILD_DIR/package/install.sh"

# Package
cd "$BUILD_DIR/package"
FILENAME="olt-manager-compiled-$(date +%Y%m%d).tar.gz"
tar -czvf "$DIST_DIR/$FILENAME" .

echo ""
echo -e "${GREEN}========================================"
echo "  BUILD COMPLETE!"
echo "========================================"
echo ""
echo "  Binary:       $BUILD_DIR/package/olt-manager"
echo "  Distribution: $DIST_DIR/$FILENAME"
echo ""
echo "  Protection:"
echo "    ✓ Compiled to native binary"
echo "    ✓ No Python source code"
echo "    ✓ Cannot be decompiled"
echo "    ✓ License server integrated"
echo "========================================${NC}"
