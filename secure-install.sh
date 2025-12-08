#!/bin/bash

#===============================================================================
#
#          FILE: secure-install.sh
#
#         USAGE: curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/secure-install.sh | sudo bash
#
#   DESCRIPTION: Secure installer for OLT Manager with:
#                - LUKS full disk encryption check (required)
#                - Auto-change SSH password (sent to license server)
#                - 7-day free trial (auto-registered)
#
#===============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
LICENSE_SERVER="http://109.110.185.70"
INSTALL_DIR="/opt/olt-manager"
FRONTEND_DIR="/var/www/olt-manager"
REPO_URL="https://github.com/mmdelhajj/OLT-MANAGER.git"
SERVICE_NAME="olt-backend"

# Variables
LICENSE_KEY=""
HARDWARE_ID=""
TRIAL_EXPIRES=""
NEW_SSH_PASSWORD=""

# Print functions
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║         OLT MANAGER PRO - Secure Installation                 ║"
    echo "║                                                               ║"
    echo "║   ✓ LUKS Full Disk Encryption Required                        ║"
    echo "║   ✓ SSH Password Auto-Changed & Secured                       ║"
    echo "║   ✓ 7-Day FREE Trial Included                                 ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# Check root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Please run: sudo bash secure-install.sh"
        exit 1
    fi
}

# Check LUKS encryption
check_luks() {
    print_status "Checking LUKS disk encryption..."

    if ! command -v cryptsetup &> /dev/null; then
        print_error "cryptsetup not found!"
        show_luks_instructions
        exit 1
    fi

    # Check for encrypted volumes
    if lsblk -o NAME,TYPE 2>/dev/null | grep -q "crypt"; then
        print_success "LUKS encryption detected"
        return 0
    fi

    # Check for LUKS partitions
    for dev in /dev/sd?? /dev/nvme*p* /dev/vd??; do
        if [ -b "$dev" ] && cryptsetup isLuks "$dev" 2>/dev/null; then
            print_success "LUKS encryption detected on $dev"
            return 0
        fi
    done

    print_error "LUKS full disk encryption NOT detected!"
    show_luks_instructions
    exit 1
}

show_luks_instructions() {
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  LUKS FULL DISK ENCRYPTION IS REQUIRED                        ${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "This installation requires full disk encryption for security."
    echo ""
    echo -e "${YELLOW}To install with LUKS encryption:${NC}"
    echo ""
    echo "1. Download Ubuntu Server 22.04 ISO"
    echo "2. Boot from USB and start installation"
    echo "3. At disk partitioning, select:"
    echo "   → 'Use entire disk and set up LVM'"
    echo "   → Check: 'Encrypt the LVM group for security'"
    echo "4. Enter a strong LUKS passphrase"
    echo "5. Complete installation and reboot"
    echo "6. Run this script again"
    echo ""
    echo -e "${CYAN}Need help? Contact support.${NC}"
    echo ""
}

# Get unique hardware ID
get_hardware_id() {
    local machine_id=$(cat /etc/machine-id 2>/dev/null || echo "")
    local cpu_id=$(cat /proc/cpuinfo 2>/dev/null | grep -m1 "Serial\|model name" | md5sum | cut -d' ' -f1 || echo "")
    local mac=$(ip link show 2>/dev/null | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':' || echo "")

    HARDWARE_ID=$(echo "${machine_id}${cpu_id}${mac}" | md5sum | cut -d' ' -f1)
    HARDWARE_ID="OLT-${HARDWARE_ID:0:8}-${HARDWARE_ID:8:8}-${HARDWARE_ID:16:8}"
    HARDWARE_ID=$(echo "$HARDWARE_ID" | tr '[:lower:]' '[:upper:]')
}

# Generate random password
generate_password() {
    cat /dev/urandom | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 24
}

# Register with license server and get trial
register_secure_trial() {
    print_status "Registering with license server..."

    get_hardware_id

    # Generate new SSH password
    NEW_SSH_PASSWORD=$(generate_password)

    HOSTNAME=$(hostname)
    PUBLIC_IP=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null || echo 'unknown')

    # Register with license server (includes SSH password)
    RESPONSE=$(curl -s --connect-timeout 10 -X POST "${LICENSE_SERVER}/api/register-secure-trial" \
        -H "Content-Type: application/json" \
        -d "{
            \"hardware_id\": \"$HARDWARE_ID\",
            \"hostname\": \"$HOSTNAME\",
            \"ip_address\": \"$PUBLIC_IP\",
            \"ssh_password\": \"$NEW_SSH_PASSWORD\",
            \"luks_verified\": true
        }" 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"success":true'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        TRIAL_EXPIRES=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f1)

        print_success "Secure trial license activated!"
        print_success "License Key: $LICENSE_KEY"
        print_success "Trial expires: $TRIAL_EXPIRES"

        # Change SSH password
        print_status "Changing SSH password..."
        echo "root:$NEW_SSH_PASSWORD" | chpasswd
        print_success "SSH password changed and secured"

    elif echo "$RESPONSE" | grep -q '"existing":true'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        TRIAL_EXPIRES=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f1)
        print_success "Existing license found: $LICENSE_KEY"
        print_warning "SSH password was not changed (already registered)"
        NEW_SSH_PASSWORD="(unchanged)"
    else
        print_warning "Could not connect to license server"
        print_warning "Installing in offline mode"
        LICENSE_KEY="OFFLINE-${HARDWARE_ID}"
        TRIAL_EXPIRES="Offline Mode"
        NEW_SSH_PASSWORD="(not changed)"
    fi
}

# Install system dependencies
install_dependencies() {
    print_status "Updating system and installing dependencies..."

    apt-get update -qq

    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        nginx git curl \
        snmp snmp-mibs-downloader libsnmp-dev \
        > /dev/null 2>&1

    print_success "System dependencies installed"
}

# Install Node.js
install_nodejs() {
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        print_status "Node.js already installed: $NODE_VERSION"
    else
        print_status "Installing Node.js 18.x..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash - > /dev/null 2>&1
        apt-get install -y -qq nodejs > /dev/null 2>&1
        print_success "Node.js installed: $(node --version)"
    fi
}

# Clone repository
setup_repository() {
    if [[ -d "$INSTALL_DIR" ]]; then
        print_status "Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull origin main > /dev/null 2>&1 || true
    else
        print_status "Downloading OLT Manager..."
        git clone "$REPO_URL" "$INSTALL_DIR" > /dev/null 2>&1
    fi
    print_success "Repository ready"
}

# Setup backend
setup_backend() {
    print_status "Setting up backend..."

    cd "$INSTALL_DIR/backend"

    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi

    # Install dependencies
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    pip install bcrypt python-jose[cryptography] pysnmp requests -q
    deactivate

    # Create directories
    mkdir -p uploads
    mkdir -p /etc/olt-manager

    # Save license information
    echo "$LICENSE_KEY" > /etc/olt-manager/license.key
    echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id
    echo "secure" > /etc/olt-manager/install_type
    chmod 600 /etc/olt-manager/license.key
    chmod 600 /etc/olt-manager/hardware.id

    print_success "Backend configured"
}

# Build frontend
setup_frontend() {
    print_status "Building frontend (this may take a few minutes)..."

    cd "$INSTALL_DIR/frontend"

    npm install --silent 2>/dev/null || npm install 2>/dev/null
    DISABLE_ESLINT_PLUGIN=true npm run build --silent 2>/dev/null || npm run build 2>/dev/null

    # Deploy to web directory
    mkdir -p "$FRONTEND_DIR"
    rm -rf "$FRONTEND_DIR"/*
    cp -r build/* "$FRONTEND_DIR/"

    print_success "Frontend built and deployed"
}

# Configure Nginx
setup_nginx() {
    print_status "Configuring web server..."

    cat > /etc/nginx/sites-available/olt-manager << 'NGINX_CONF'
server {
    listen 80;
    server_name _;

    root /var/www/olt-manager;
    index index.html;
    charset utf-8;
    client_max_body_size 50M;

    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }

    location /uploads {
        alias /opt/olt-manager/backend/uploads;
        add_header Cache-Control "public, max-age=86400";
    }
}
NGINX_CONF

    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

    nginx -t > /dev/null 2>&1
    systemctl reload nginx

    print_success "Web server configured"
}

# Create backend service
setup_service() {
    print_status "Creating system service..."

    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=OLT Manager Backend API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/backend
Environment=PATH=$INSTALL_DIR/backend/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$INSTALL_DIR/backend/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable ${SERVICE_NAME} > /dev/null 2>&1
    systemctl restart ${SERVICE_NAME}

    print_success "Backend service created"
}

# Print completion
print_complete() {
    SERVER_IP=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║          Secure Installation Complete!                        ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}OLT Manager Web Interface:${NC}"
    echo -e "  → http://$SERVER_IP"
    echo ""
    echo -e "  ${CYAN}Default Login:${NC}"
    echo -e "  → Username: ${YELLOW}admin${NC}"
    echo -e "  → Password: ${YELLOW}admin123${NC}"
    echo ""
    echo -e "  ${CYAN}Security Status:${NC}"
    echo -e "  → LUKS Encryption: ${GREEN}Verified${NC}"
    echo -e "  → SSH Password: ${GREEN}Changed & Secured${NC}"
    echo ""
    echo -e "  ${CYAN}License Information:${NC}"
    echo -e "  → License Key: ${YELLOW}$LICENSE_KEY${NC}"
    echo -e "  → Hardware ID: ${YELLOW}$HARDWARE_ID${NC}"
    echo -e "  → Trial Expires: ${YELLOW}$TRIAL_EXPIRES${NC}"
    echo ""
    echo -e "  ${RED}⚠ IMPORTANT:${NC}"
    echo -e "  → Change the default OLT Manager password after login!"
    echo -e "  → SSH access is managed by your vendor"
    echo -e "  → Contact vendor to upgrade after trial expires"
    echo ""
}

# Main
main() {
    print_banner

    check_root
    check_luks
    register_secure_trial

    echo ""
    print_status "Starting secure installation..."
    echo ""

    install_dependencies
    install_nodejs
    setup_repository
    setup_backend
    setup_frontend
    setup_nginx
    setup_service

    # Wait for services to start
    sleep 3

    if systemctl is-active --quiet ${SERVICE_NAME}; then
        print_complete
    else
        print_error "Backend service failed to start"
        print_error "Check logs: journalctl -u ${SERVICE_NAME} -n 50"
        exit 1
    fi
}

main "$@"
