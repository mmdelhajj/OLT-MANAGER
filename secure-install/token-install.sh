#!/bin/bash

#===============================================================================
#
#          FILE: token-install.sh
#
#         USAGE: curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/secure-install/token-install.sh | bash -s -- <INSTALL_TOKEN>
#
#   DESCRIPTION: Token-based secure installer for OLT Manager
#                - Validates install token with license server
#                - Auto-changes SSH password (sent to license server)
#                - Sets up reverse SSH tunnel
#                - Requires LUKS full disk encryption
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
LICENSE_SERVER="http://lic.proxpanel.com"
INSTALL_DIR="/opt/olt-manager"
FRONTEND_DIR="/var/www/olt-manager"
REPO_URL="https://github.com/mmdelhajj/OLT-MANAGER.git"
SERVICE_NAME="olt-backend"
TUNNEL_SERVICE="olt-tunnel"

# Variables (set during token validation)
LICENSE_KEY=""
CUSTOMER_NAME=""
TUNNEL_PORT=""
NEW_SSH_PASSWORD=""

# Print functions
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║         OLT MANAGER PRO - Secure Installation                 ║"
    echo "║                                                               ║"
    echo "║   ✓ LUKS Full Disk Encryption Required                        ║"
    echo "║   ✓ SSH Password Auto-Changed                                 ║"
    echo "║   ✓ Reverse Tunnel for Remote Support                         ║"
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
        echo "Please run: sudo bash -s -- $INSTALL_TOKEN"
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
    echo "6. Run this script again with your token"
    echo ""
    echo -e "${CYAN}Need help? Contact support.${NC}"
    echo ""
}

# Validate install token with license server
validate_token() {
    local TOKEN="$1"

    if [[ -z "$TOKEN" ]]; then
        print_error "Install token required!"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/secure-install/token-install.sh | bash -s -- YOUR_TOKEN"
        echo ""
        echo "Get your install token from your vendor."
        exit 1
    fi

    print_status "Validating install token..."

    RESPONSE=$(curl -s -X POST "${LICENSE_SERVER}/api/validate-install-token" \
        -H "Content-Type: application/json" \
        -d "{\"token\": \"$TOKEN\"}" 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"valid":true'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        CUSTOMER_NAME=$(echo "$RESPONSE" | grep -o '"customer_name":"[^"]*"' | cut -d'"' -f4)
        TUNNEL_PORT=$(echo "$RESPONSE" | grep -o '"tunnel_port":[0-9]*' | cut -d':' -f2)

        print_success "Token valid!"
        print_success "Customer: $CUSTOMER_NAME"
        print_success "Tunnel Port: $TUNNEL_PORT"
    else
        ERROR=$(echo "$RESPONSE" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
        print_error "Invalid install token!"
        if [[ -n "$ERROR" ]]; then
            print_error "Reason: $ERROR"
        fi
        exit 1
    fi
}

# Generate random password
generate_password() {
    # 24 character random password with special chars
    cat /dev/urandom | tr -dc 'A-Za-z0-9!@#$%^&*()_+' | head -c 24
}

# Change SSH password and send to license server
setup_ssh_security() {
    print_status "Setting up SSH security..."

    # Generate random password
    NEW_SSH_PASSWORD=$(generate_password)

    # Change root password
    echo "root:$NEW_SSH_PASSWORD" | chpasswd

    # Get system info
    HOSTNAME=$(hostname)
    HARDWARE_ID=$(cat /etc/machine-id 2>/dev/null | head -c 32 || echo "unknown")
    PUBLIC_IP=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null || echo 'unknown')

    # Send credentials to license server
    print_status "Registering installation with license server..."

    SEND_RESULT=$(curl -s -X POST "${LICENSE_SERVER}/api/register-installation" \
        -H "Content-Type: application/json" \
        -d "{
            \"license_key\": \"$LICENSE_KEY\",
            \"tunnel_port\": $TUNNEL_PORT,
            \"ssh_password\": \"$NEW_SSH_PASSWORD\",
            \"hostname\": \"$HOSTNAME\",
            \"hardware_id\": \"$HARDWARE_ID\",
            \"ip_address\": \"$PUBLIC_IP\"
        }" 2>/dev/null)

    if echo "$SEND_RESULT" | grep -q '"success":true'; then
        print_success "Installation registered with license server"
    else
        print_warning "Could not register with license server (will retry on tunnel connect)"
    fi

    print_success "SSH password changed and stored securely"
}

# Install system dependencies
install_dependencies() {
    print_status "Updating system and installing dependencies..."

    apt-get update -qq

    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        nginx git curl \
        snmp snmp-mibs-downloader libsnmp-dev \
        autossh \
        > /dev/null 2>&1

    print_success "System dependencies installed"
}

# Install Node.js
install_nodejs() {
    if command -v node &> /dev/null; then
        print_status "Node.js already installed: $(node --version)"
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
        print_status "Cloning OLT Manager..."
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
    pip install bcrypt python-jose[cryptography] pysnmp -q
    deactivate

    # Create directories
    mkdir -p uploads
    mkdir -p /etc/olt-manager

    # Save license key
    echo "$LICENSE_KEY" > /etc/olt-manager/license.key
    chmod 600 /etc/olt-manager/license.key

    # Save tunnel port
    echo "$TUNNEL_PORT" > /etc/olt-manager/tunnel_port
    chmod 600 /etc/olt-manager/tunnel_port

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
    print_status "Creating system services..."

    # Backend service
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

# Setup reverse SSH tunnel
setup_tunnel() {
    print_status "Setting up remote support tunnel..."

    # Install sshpass for tunnel authentication
    apt-get install -y -qq sshpass > /dev/null 2>&1

    # Create tunnel script with password authentication
    cat > /usr/local/bin/olt-tunnel << 'TUNNEL_EOF'
#!/bin/bash
# OLT Manager Reverse SSH Tunnel
# Connects to license server for remote support

LICENSE_SERVER="lic.proxpanel.com"
TUNNEL_PORT=$(cat /etc/olt-manager/tunnel_port 2>/dev/null || echo "30001")

# Register with license server on each connection
register_tunnel() {
    curl -s -X POST "http://${LICENSE_SERVER}/api/register-tunnel" \
        -H "Content-Type: application/json" \
        -d "{\"port\": $TUNNEL_PORT, \"license_key\": \"$(cat /etc/olt-manager/license.key 2>/dev/null)\", \"hostname\": \"$(hostname)\"}" \
        > /dev/null 2>&1
}

while true; do
    register_tunnel

    # Try reverse tunnel using sshpass for password auth
    export SSHPASS="tunnel123"
    sshpass -e ssh -N \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o ConnectTimeout=10 \
        -R ${TUNNEL_PORT}:127.0.0.1:22 \
        -p 2222 tunnel@${LICENSE_SERVER} 2>/dev/null

    # If failed, wait and retry
    sleep 10
done
TUNNEL_EOF
    chmod +x /usr/local/bin/olt-tunnel

    # Create systemd service for tunnel
    cat > /etc/systemd/system/${TUNNEL_SERVICE}.service << EOF
[Unit]
Description=OLT Manager Remote Support Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/olt-tunnel
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable ${TUNNEL_SERVICE} > /dev/null 2>&1
    systemctl start ${TUNNEL_SERVICE} 2>/dev/null || true

    print_success "Remote support tunnel configured (Port: $TUNNEL_PORT)"
}

# Print completion
print_complete() {
    SERVER_IP=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║          Installation Complete!                               ║${NC}"
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
    echo -e "  → LUKS Encryption: ${GREEN}Active${NC}"
    echo -e "  → SSH Password: ${GREEN}Changed & Secured${NC}"
    echo -e "  → Remote Support: ${GREEN}Tunnel Port $TUNNEL_PORT${NC}"
    echo ""
    echo -e "  ${CYAN}License:${NC}"
    echo -e "  → Key: ${YELLOW}$LICENSE_KEY${NC}"
    echo -e "  → Customer: ${YELLOW}$CUSTOMER_NAME${NC}"
    echo ""
    echo -e "  ${RED}⚠ IMPORTANT:${NC}"
    echo -e "  → Change default OLT Manager password after login!"
    echo -e "  → SSH access is managed by your vendor"
    echo ""
}

# Main
main() {
    print_banner

    INSTALL_TOKEN="$1"

    check_root
    check_luks
    validate_token "$INSTALL_TOKEN"

    echo ""
    print_status "Starting secure installation..."
    echo ""

    setup_ssh_security
    install_dependencies
    install_nodejs
    setup_repository
    setup_backend
    setup_frontend
    setup_nginx
    setup_service
    setup_tunnel

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
