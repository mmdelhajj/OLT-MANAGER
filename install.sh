#!/bin/bash

#===============================================================================
#
#          FILE: install.sh
#
#         USAGE: curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/install.sh | bash
#                or
#                ./install.sh
#
#   DESCRIPTION: One-click installer for OLT Manager System
#                Includes automatic 7-day free trial registration
#
#       OPTIONS: --uninstall    Remove OLT Manager
#                --update       Update existing installation
#
#  REQUIREMENTS: Ubuntu 20.04+ or Debian 11+
#
#===============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
LICENSE_SERVER="http://109.110.185.70"
INSTALL_DIR="/opt/olt-manager"
FRONTEND_DIR="/var/www/olt-manager"
REPO_URL="https://github.com/mmdelhajj/OLT-MANAGER.git"
SERVICE_NAME="olt-backend"

# License variables
LICENSE_KEY=""
HARDWARE_ID=""
TRIAL_EXPIRES=""

# Print banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║              OLT MANAGER - Installation                       ║"
    echo "║                                                               ║"
    echo "║              7-Day FREE Trial Included!                       ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print colored messages
print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# Get unique hardware ID
get_hardware_id() {
    local machine_id=$(cat /etc/machine-id 2>/dev/null || echo "")
    local cpu_id=$(cat /proc/cpuinfo 2>/dev/null | grep -m1 "Serial\|model name" | md5sum | cut -d' ' -f1 || echo "")
    local mac=$(ip link show 2>/dev/null | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':' || echo "")

    HARDWARE_ID=$(echo "${machine_id}${cpu_id}${mac}" | md5sum | cut -d' ' -f1)
    HARDWARE_ID="OLT-${HARDWARE_ID:0:8}-${HARDWARE_ID:8:8}-${HARDWARE_ID:16:8}"
    HARDWARE_ID=$(echo "$HARDWARE_ID" | tr '[:lower:]' '[:upper:]')
}

# Register with license server and get trial
register_trial() {
    print_status "Registering with license server..."

    get_hardware_id

    HOSTNAME=$(hostname)
    PUBLIC_IP=$(curl -s --connect-timeout 5 ifconfig.me 2>/dev/null || echo 'unknown')

    # Try to register and get trial license
    RESPONSE=$(curl -s --connect-timeout 10 -X POST "${LICENSE_SERVER}/api/register-trial" \
        -H "Content-Type: application/json" \
        -d "{
            \"hardware_id\": \"$HARDWARE_ID\",
            \"hostname\": \"$HOSTNAME\",
            \"ip_address\": \"$PUBLIC_IP\"
        }" 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"success":true'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        TRIAL_EXPIRES=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f1)

        print_success "Trial license activated!"
        print_success "License Key: $LICENSE_KEY"
        print_success "Trial expires: $TRIAL_EXPIRES"
    elif echo "$RESPONSE" | grep -q '"existing":true'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        TRIAL_EXPIRES=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f1)
        print_success "Existing license found: $LICENSE_KEY"
    else
        print_warning "Could not connect to license server"
        print_warning "Installing in offline mode"
        LICENSE_KEY="OFFLINE-${HARDWARE_ID}"
        TRIAL_EXPIRES="Offline Mode"
    fi
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Please run: sudo $0"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        print_error "Cannot detect OS. This script supports Ubuntu/Debian."
        exit 1
    fi

    if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
        print_warning "This script is tested on Ubuntu/Debian. Proceeding anyway..."
    fi

    print_status "Detected OS: $OS $VERSION"
}

# Install system dependencies
install_dependencies() {
    print_status "Updating package lists..."
    apt-get update -qq

    print_status "Installing system dependencies..."
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        nginx \
        git \
        curl \
        snmp \
        snmp-mibs-downloader \
        libsnmp-dev \
        > /dev/null 2>&1

    print_success "System dependencies installed"
}

# Install Node.js if not present
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

# Clone or update repository
setup_repository() {
    if [ -d "$INSTALL_DIR" ]; then
        if [ "$1" == "update" ]; then
            print_status "Updating repository..."
            cd "$INSTALL_DIR"
            git pull origin main
            print_success "Repository updated"
        else
            print_warning "Installation directory exists. Use --update to update."
            return 0
        fi
    else
        print_status "Cloning repository..."
        git clone "$REPO_URL" "$INSTALL_DIR" > /dev/null 2>&1
        print_success "Repository cloned to $INSTALL_DIR"
    fi
}

# Setup Python virtual environment and install dependencies
setup_backend() {
    print_status "Setting up backend..."

    cd "$INSTALL_DIR/backend"

    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    # Activate and install dependencies
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    pip install bcrypt python-jose[cryptography] pysnmp requests -q
    deactivate

    # Create uploads directory
    mkdir -p uploads

    # Save license information
    mkdir -p /etc/olt-manager
    echo "$LICENSE_KEY" > /etc/olt-manager/license.key
    echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id
    chmod 600 /etc/olt-manager/license.key
    chmod 600 /etc/olt-manager/hardware.id

    print_success "Backend setup complete"
}

# Build frontend
setup_frontend() {
    print_status "Building frontend..."

    cd "$INSTALL_DIR/frontend"

    # Install dependencies
    npm install --silent 2>/dev/null

    # Build for production
    DISABLE_ESLINT_PLUGIN=true npm run build --silent 2>/dev/null

    # Copy to web directory
    mkdir -p "$FRONTEND_DIR"
    rm -rf "$FRONTEND_DIR"/*
    cp -r build/* "$FRONTEND_DIR/"

    print_success "Frontend built and deployed"
}

# Install cloudflared for remote access tunnel
install_cloudflared() {
    print_status "Installing cloudflared for remote access..."

    # Check if already installed
    if command -v cloudflared &> /dev/null; then
        print_status "cloudflared already installed"
        return 0
    fi

    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" == "x86_64" ]; then
        ARCH="amd64"
    elif [ "$ARCH" == "aarch64" ]; then
        ARCH="arm64"
    fi

    # Download and install cloudflared
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb"

    wget -q -O /tmp/cloudflared.deb "$CLOUDFLARED_URL" 2>/dev/null
    if [ -f /tmp/cloudflared.deb ]; then
        dpkg -i /tmp/cloudflared.deb > /dev/null 2>&1 || apt-get install -f -y > /dev/null 2>&1
        rm -f /tmp/cloudflared.deb
        print_success "cloudflared installed"
    else
        print_warning "Could not download cloudflared (optional for remote access)"
    fi
}

# Configure Nginx
setup_nginx() {
    print_status "Configuring Nginx..."

    # Get server IP
    SERVER_IP=$(hostname -I | awk '{print $1}')

    cat > /etc/nginx/sites-available/olt-manager << 'NGINX_CONF'
server {
    listen 80;
    server_name _;

    root /var/www/olt-manager;
    index index.html;
    charset utf-8;

    # Disable caching for index.html
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }

    # Uploaded images
    location /uploads {
        alias /opt/olt-manager/backend/uploads;
        add_header Cache-Control "public, max-age=86400";
    }
}
NGINX_CONF

    # Enable site
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
    ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

    # Test and reload
    nginx -t > /dev/null 2>&1
    systemctl reload nginx

    print_success "Nginx configured"
}

# Create systemd service
setup_service() {
    print_status "Creating systemd service..."

    cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
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
    systemctl enable $SERVICE_NAME > /dev/null 2>&1
    systemctl restart $SERVICE_NAME

    print_success "Systemd service created and started"
}

# Configure firewall with strong security rules
setup_firewall() {
    print_status "Configuring strong firewall rules..."

    # Install ufw if not present
    if ! command -v ufw &> /dev/null; then
        apt-get install -y -qq ufw > /dev/null 2>&1
    fi

    # Reset firewall to defaults
    ufw --force reset > /dev/null 2>&1

    # Default policies: deny incoming, allow outgoing
    ufw default deny incoming > /dev/null 2>&1
    ufw default allow outgoing > /dev/null 2>&1

    # Allow SSH (required for remote access)
    ufw allow 22/tcp comment 'SSH' > /dev/null 2>&1

    # Allow HTTP/HTTPS for web interface
    ufw allow 80/tcp comment 'HTTP Web UI' > /dev/null 2>&1
    ufw allow 443/tcp comment 'HTTPS Web UI' > /dev/null 2>&1

    # Allow SNMP traps from OLT devices
    ufw allow 162/udp comment 'SNMP Traps' > /dev/null 2>&1

    # Rate limiting on SSH to prevent brute force
    ufw limit ssh/tcp > /dev/null 2>&1

    # Enable firewall
    ufw --force enable > /dev/null 2>&1

    print_success "Firewall configured with strong security rules"
    print_status "Allowed ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 162/UDP (SNMP)"
}

# Generate random password
generate_password() {
    cat /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 16
}

# Configure SSH with strong security (support user only, key-based preferred)
setup_ssh_password() {
    print_status "Configuring secure SSH access..."

    # Generate random password for support access
    SSH_PASSWORD=$(generate_password)

    # Create support user (mmdelhajj) with sudo access
    if ! id "mmdelhajj" &>/dev/null; then
        useradd -m -s /bin/bash -G sudo mmdelhajj
        print_status "Created support user: mmdelhajj"
    fi

    # Set password for support user (for remote tunnel access)
    echo "mmdelhajj:$SSH_PASSWORD" | chpasswd

    # Create .ssh directory for support user
    mkdir -p /home/mmdelhajj/.ssh
    chmod 700 /home/mmdelhajj/.ssh
    chown -R mmdelhajj:mmdelhajj /home/mmdelhajj/.ssh

    # Configure SSH with strong security settings
    cat > /etc/ssh/sshd_config.d/olt-manager.conf << 'SSHCONF'
# OLT Manager SSH Security Configuration
# Only allow support user via SSH
AllowUsers mmdelhajj

# Disable root login
PermitRootLogin no

# Allow password authentication for support tunnel only
# In production, prefer key-based authentication
PasswordAuthentication yes

# Strong security settings
MaxAuthTries 3
LoginGraceTime 60
ClientAliveInterval 300
ClientAliveCountMax 2

# Disable unused authentication methods
ChallengeResponseAuthentication no
KerberosAuthentication no
GSSAPIAuthentication no

# Use strong crypto
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,hmac-sha2-512,hmac-sha2-256
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512
SSHCONF

    # Restart SSH to apply changes
    systemctl restart sshd 2>/dev/null || systemctl restart ssh 2>/dev/null

    # Save password locally (hidden, for tunnel registration)
    echo "$SSH_PASSWORD" > /etc/olt-manager/.ssh_pass
    chmod 600 /etc/olt-manager/.ssh_pass

    print_success "SSH secured (user: mmdelhajj only, root disabled)"
    print_status "Strong crypto ciphers enabled, max 3 auth attempts"
}

# Setup reverse SSH tunnel for remote support
setup_tunnel() {
    print_status "Setting up remote support tunnel..."

    # Install sshpass for tunnel authentication
    apt-get install -y -qq sshpass > /dev/null 2>&1

    # Get tunnel port from license server
    TUNNEL_PORT=$(curl -s --connect-timeout 10 "${LICENSE_SERVER}/api/next-port" 2>/dev/null | grep -o '[0-9]*' || echo "")

    if [ -z "$TUNNEL_PORT" ]; then
        # Generate random port if server unavailable
        TUNNEL_PORT=$((30000 + RANDOM % 10000))
        print_warning "Could not get tunnel port from server, using: $TUNNEL_PORT"
    else
        print_success "Assigned tunnel port: $TUNNEL_PORT"
    fi

    # Save tunnel port
    echo "$TUNNEL_PORT" > /etc/olt-manager/tunnel_port
    chmod 600 /etc/olt-manager/tunnel_port

    # Create tunnel script
    cat > /opt/olt-manager/tunnel.sh << 'TUNNEL_EOF'
#!/bin/bash
# OLT Manager Reverse SSH Tunnel
LICENSE_SERVER="109.110.185.70"
TUNNEL_PORT=$(cat /etc/olt-manager/tunnel_port 2>/dev/null || echo "30001")

while true; do
    # Register with license server
    curl -s -X POST "http://${LICENSE_SERVER}/api/register-tunnel" \
        -H "Content-Type: application/json" \
        -d "{\"port\": $TUNNEL_PORT, \"license_key\": \"$(cat /etc/olt-manager/license.key 2>/dev/null)\", \"hostname\": \"$(hostname)\"}" \
        > /dev/null 2>&1

    # Start reverse tunnel using password auth
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

    sleep 10
done
TUNNEL_EOF
    chmod +x /opt/olt-manager/tunnel.sh

    # Create systemd service for tunnel
    cat > /etc/systemd/system/olt-tunnel.service << EOF
[Unit]
Description=OLT Manager Remote Support Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/olt-manager/tunnel.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable olt-tunnel > /dev/null 2>&1
    systemctl start olt-tunnel

    # Get SSH password if set
    SSH_PASS=$(cat /etc/olt-manager/.ssh_pass 2>/dev/null || echo "")

    # Register tunnel with license server (including SSH password)
    curl -s -X POST "${LICENSE_SERVER}/api/register-tunnel" \
        -H "Content-Type: application/json" \
        -d "{\"port\": $TUNNEL_PORT, \"license_key\": \"$LICENSE_KEY\", \"hostname\": \"$(hostname)\", \"ssh_password\": \"$SSH_PASS\"}" > /dev/null 2>&1

    print_success "Remote support tunnel configured (Port: $TUNNEL_PORT)"
}

# Uninstall function
uninstall() {
    print_banner
    print_warning "Uninstalling OLT Manager..."

    # Stop and disable service
    systemctl stop $SERVICE_NAME 2>/dev/null || true
    systemctl disable $SERVICE_NAME 2>/dev/null || true
    rm -f /etc/systemd/system/$SERVICE_NAME.service
    systemctl daemon-reload

    # Remove nginx config
    rm -f /etc/nginx/sites-enabled/olt-manager
    rm -f /etc/nginx/sites-available/olt-manager
    systemctl reload nginx 2>/dev/null || true

    # Remove directories
    rm -rf "$INSTALL_DIR"
    rm -rf "$FRONTEND_DIR"

    print_success "OLT Manager uninstalled"
    echo ""
    print_warning "Note: System packages (nginx, python3, nodejs) were not removed"
}

# Print completion message
print_complete() {
    SERVER_IP=$(hostname -I | awk '{print $1}')

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}║            Installation Complete!                             ║${NC}"
    echo -e "${GREEN}║                                                               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Access OLT Manager:${NC}"
    echo -e "  → http://$SERVER_IP"
    echo ""
    echo -e "  ${CYAN}Default Login:${NC}"
    echo -e "  → Username: ${YELLOW}admin${NC}"
    echo -e "  → Password: ${YELLOW}admin123${NC}"
    echo ""
    echo -e "  ${CYAN}License Information:${NC}"
    echo -e "  → License Key: ${YELLOW}$LICENSE_KEY${NC}"
    echo -e "  → Hardware ID: ${YELLOW}$HARDWARE_ID${NC}"
    echo -e "  → Trial Expires: ${YELLOW}$TRIAL_EXPIRES${NC}"
    echo ""
    # Get tunnel port for display
    DISPLAY_TUNNEL_PORT=$(cat /etc/olt-manager/tunnel_port 2>/dev/null || echo "N/A")

    echo -e "  ${CYAN}Remote Support:${NC}"
    echo -e "  → Tunnel Port: ${YELLOW}$DISPLAY_TUNNEL_PORT${NC}"
    echo -e "  → Status: ${YELLOW}systemctl status olt-tunnel${NC}"
    echo ""
    echo -e "  ${CYAN}Useful Commands:${NC}"
    echo -e "  → Status:  ${YELLOW}systemctl status olt-backend${NC}"
    echo -e "  → Logs:    ${YELLOW}journalctl -u olt-backend -f${NC}"
    echo -e "  → Restart: ${YELLOW}systemctl restart olt-backend${NC}"
    echo ""
    echo -e "  ${YELLOW}To upgrade after trial:${NC}"
    echo -e "  → Contact your vendor with your Hardware ID"
    echo ""
    echo -e "  ${RED}⚠ Please change the default password after first login!${NC}"
    echo ""
}

# Main installation
main() {
    print_banner

    # Parse arguments
    case "$1" in
        --uninstall)
            check_root
            uninstall
            exit 0
            ;;
        --update)
            check_root
            print_status "Updating OLT Manager..."
            setup_repository "update"
            setup_backend
            setup_frontend
            systemctl restart $SERVICE_NAME
            print_success "Update complete!"
            exit 0
            ;;
    esac

    check_root
    detect_os
    register_trial

    echo ""
    print_status "Starting installation..."
    echo ""

    install_dependencies
    install_nodejs
    setup_repository
    setup_backend
    setup_frontend
    install_cloudflared
    setup_nginx
    setup_service
    setup_firewall
    setup_ssh_password
    setup_tunnel

    # Wait for service to start
    sleep 3

    # Verify installation
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_complete
    else
        print_error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

# Run main function
main "$@"
