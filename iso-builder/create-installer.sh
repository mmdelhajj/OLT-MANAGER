#!/bin/bash
#
# OLT Manager Installer Package Creator
# Creates a self-extracting installer that can be run on any Ubuntu 22.04+ system
#

set -e

# Configuration
VERSION=$(cat /root/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
OUTPUT_DIR="/root/olt-manager/iso-builder/output"
PACKAGE_NAME="olt-manager-installer-${VERSION}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[X]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       OLT Manager Self-Extracting Installer Creator          ║"
echo "║                    Version $VERSION                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"
WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

print_status "Preparing installer package..."

# Create package directory structure
mkdir -p "$WORK_DIR/olt-manager"/{backend,scripts}

# Copy backend files
print_status "Copying backend files..."
cp -r /root/olt-manager/backend/* "$WORK_DIR/olt-manager/backend/"

# Remove unnecessary files from backend
rm -rf "$WORK_DIR/olt-manager/backend/__pycache__" 2>/dev/null || true
rm -rf "$WORK_DIR/olt-manager/backend/venv" 2>/dev/null || true
rm -rf "$WORK_DIR/olt-manager/backend/data" 2>/dev/null || true
rm -f "$WORK_DIR/olt-manager/backend"/*.pyc 2>/dev/null || true
find "$WORK_DIR/olt-manager/backend" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Copy console menu
print_status "Copying console menu..."
cp /root/olt-manager/iso-builder/olt-console.sh "$WORK_DIR/olt-manager/scripts/olt-console.sh"

# Copy frontend if it exists
if [[ -d /var/www/html ]] && [[ -f /var/www/html/index.html ]]; then
    print_status "Copying frontend files..."
    mkdir -p "$WORK_DIR/olt-manager/frontend"
    cp -r /var/www/html/* "$WORK_DIR/olt-manager/frontend/"
fi

# Create the installation script
print_status "Creating installation script..."
cat > "$WORK_DIR/olt-manager/install.sh" << 'INSTALL_SCRIPT'
#!/bin/bash
#
# OLT Manager Appliance Installer
# Run this script on a fresh Ubuntu 22.04+ server
#

set -e

export DEBIAN_FRONTEND=noninteractive

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[X]${NC} $1"; }

clear
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}          OLT Manager Appliance Installer                     ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                    Version INSTALLER_VERSION                            ${BLUE}║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

# Check Ubuntu version
if [[ ! -f /etc/os-release ]]; then
    print_error "Cannot detect OS version"
    exit 1
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
    print_warning "This installer is designed for Ubuntu/Debian. Proceeding anyway..."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_status "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

print_status "Installing required packages..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    snmp \
    snmp-mibs-downloader \
    curl \
    wget \
    net-tools \
    iproute2 \
    openssh-server \
    sshpass \
    sqlite3

# Create directories
print_status "Creating directories..."
mkdir -p /opt/olt-manager
mkdir -p /etc/olt-manager
mkdir -p /var/www/html

# Copy backend
print_status "Installing backend..."
cp -r "$SCRIPT_DIR/backend" /opt/olt-manager/

# Setup Python virtual environment
print_status "Setting up Python environment..."
cd /opt/olt-manager/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>/dev/null || \
    pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt python-multipart aiofiles requests paramiko pysnmp -q

# Copy frontend if available
if [[ -d "$SCRIPT_DIR/frontend" ]]; then
    print_status "Installing frontend..."
    cp -r "$SCRIPT_DIR/frontend"/* /var/www/html/
else
    echo "<h1>OLT Manager</h1><p>Frontend loading...</p>" > /var/www/html/index.html
fi

# Install console menu
print_status "Installing console menu..."
cp "$SCRIPT_DIR/scripts/olt-console.sh" /usr/local/bin/olt-console
chmod +x /usr/local/bin/olt-console

# Create systemd service
print_status "Creating systemd service..."
cat > /etc/systemd/system/olt-manager.service << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/olt-manager/backend
Environment=PATH=/opt/olt-manager/backend/venv/bin:/usr/bin:/bin
ExecStart=/opt/olt-manager/backend/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
print_status "Configuring Nginx..."
cat > /etc/nginx/sites-available/olt-manager << 'EOF'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 50M;

    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

# Configure auto-login console menu
print_status "Configuring console menu..."
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
Type=idle
EOF

cat > /root/.bash_profile << 'EOF'
# OLT Manager Console
if [[ $(tty) == /dev/tty1 ]]; then
    /usr/local/bin/olt-console
fi
EOF

# Create first boot script
print_status "Creating first boot configuration..."
cat > /opt/olt-manager/firstboot.sh << 'FIRSTBOOT'
#!/bin/bash
# Generate hardware ID and register
mkdir -p /etc/olt-manager

MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "unknown")
MAC=$(ip link show 2>/dev/null | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':')
FINGERPRINT="${MACHINE_ID}${MAC}"
HASH=$(echo -n "$FINGERPRINT" | md5sum | cut -d' ' -f1)
HARDWARE_ID="OLT-${HASH:0:8}-${HASH:8:8}-${HASH:16:8}"
echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id
chmod 600 /etc/olt-manager/hardware.id

# Register trial license
curl -s -X POST "http://lic.proxpanel.com/api/register-trial" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}" > /dev/null 2>&1

# Register tunnel for remote management
RESPONSE=$(curl -s -X POST "http://lic.proxpanel.com/api/tunnel/register" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}" 2>/dev/null)

TUNNEL_PORT=$(echo "$RESPONSE" | grep -o '"port":[0-9]*' | cut -d':' -f2)
if [[ -n "$TUNNEL_PORT" ]]; then
    cat > /opt/olt-manager/tunnel.sh << EOF
#!/bin/bash
export SSHPASS="yo3nFHoe5TXNcEDdTV85"
exec sshpass -e ssh -N -R ${TUNNEL_PORT}:localhost:22 -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -p 2222 tunnel@lic.proxpanel.com
EOF
    chmod +x /opt/olt-manager/tunnel.sh
    systemctl enable olt-tunnel 2>/dev/null
    systemctl start olt-tunnel 2>/dev/null
fi

touch /etc/olt-manager/.firstboot_done
FIRSTBOOT
chmod +x /opt/olt-manager/firstboot.sh

# Create first boot service
cat > /etc/systemd/system/olt-firstboot.service << 'EOF'
[Unit]
Description=OLT Manager First Boot
After=network-online.target
Wants=network-online.target
ConditionPathExists=!/etc/olt-manager/.firstboot_done

[Service]
Type=oneshot
ExecStart=/opt/olt-manager/firstboot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Create tunnel service
cat > /etc/systemd/system/olt-tunnel.service << 'EOF'
[Unit]
Description=OLT Manager Remote Tunnel
After=network-online.target
Wants=network-online.target
ConditionPathExists=/opt/olt-manager/tunnel.sh

[Service]
Type=simple
ExecStart=/opt/olt-manager/tunnel.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Enable services
print_status "Enabling services..."
systemctl daemon-reload
systemctl enable olt-manager
systemctl enable nginx
systemctl enable ssh
systemctl enable olt-firstboot

# Start services
print_status "Starting services..."
systemctl start olt-manager
systemctl start nginx

# Run first boot
print_status "Running first boot setup..."
/opt/olt-manager/firstboot.sh

# Get IP address
IP_ADDR=$(ip -4 addr show scope global | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}              Installation Complete!                          ${GREEN}║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Web Interface: http://${IP_ADDR:-<your-ip>}                           ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Default Login: admin / admin                               ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Console Menu: Available on TTY1 or run 'olt-console'        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Hardware ID: $(cat /etc/olt-manager/hardware.id 2>/dev/null || echo 'Generating...')    ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Please change the default password after first login!${NC}"
echo ""
INSTALL_SCRIPT

# Replace version placeholder
VERSION_ESCAPED=$(echo "$VERSION" | sed 's/\./\\./g')
sed -i "s/INSTALLER_VERSION/$VERSION/g" "$WORK_DIR/olt-manager/install.sh"
chmod +x "$WORK_DIR/olt-manager/install.sh"

# Create the self-extracting package
print_status "Creating self-extracting installer..."

INSTALLER_FILE="$OUTPUT_DIR/${PACKAGE_NAME}.run"

# Create the header script
cat > "$WORK_DIR/header.sh" << 'HEADER'
#!/bin/bash
#
# OLT Manager Self-Extracting Installer
# Run with: sudo bash installer.run
#

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          OLT Manager Self-Extracting Installer               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [[ $EUID -ne 0 ]]; then
    echo "[X] This installer must be run as root"
    echo "    Usage: sudo bash $0"
    exit 1
fi

# Create temp directory
EXTRACT_DIR=$(mktemp -d)
trap "rm -rf $EXTRACT_DIR" EXIT

echo "[*] Extracting files..."

# Find the line where the archive starts
ARCHIVE_START=$(awk '/^__ARCHIVE_MARKER__$/{print NR + 1; exit 0;}' "$0")

# Extract the archive
tail -n +$ARCHIVE_START "$0" | tar -xzf - -C "$EXTRACT_DIR"

echo "[*] Starting installation..."
cd "$EXTRACT_DIR/olt-manager"
bash install.sh

exit 0

__ARCHIVE_MARKER__
HEADER

# Create the tarball
print_status "Compressing package..."
cd "$WORK_DIR"
tar -czf archive.tar.gz olt-manager

# Combine header and archive
cat header.sh archive.tar.gz > "$INSTALLER_FILE"
chmod +x "$INSTALLER_FILE"

# Get file size
INSTALLER_SIZE=$(du -h "$INSTALLER_FILE" | cut -f1)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Installer Package Created!                      ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  File: $INSTALLER_FILE"
echo "║  Size: $INSTALLER_SIZE"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Installation Instructions:                                  ║"
echo "║  1. Copy installer to fresh Ubuntu 22.04 server              ║"
echo "║  2. Run: sudo bash ${PACKAGE_NAME}.run                ║"
echo "║  3. Access web interface at http://<server-ip>               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
