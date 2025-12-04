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
INSTALL_DIR="/opt/olt-manager"
FRONTEND_DIR="/var/www/olt-manager"
REPO_URL="https://github.com/mmdelhajj/OLT-MANAGER.git"
SERVICE_NAME="olt-backend"

# Print banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║              OLT MANAGER - Installation Script                ║"
    echo "║                                                               ║"
    echo "║   Manage your OLTs and ONUs with ease                         ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Print colored messages
print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

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
    pip install bcrypt python-jose[cryptography] pysnmp -q
    deactivate

    # Create uploads directory
    mkdir -p uploads

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

# Configure firewall
setup_firewall() {
    if command -v ufw &> /dev/null; then
        print_status "Configuring firewall..."
        ufw allow 80/tcp > /dev/null 2>&1 || true
        ufw allow 443/tcp > /dev/null 2>&1 || true
        ufw allow 162/udp > /dev/null 2>&1 || true  # SNMP traps
        print_success "Firewall configured"
    fi
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
    echo -e "  → Password: ${YELLOW}admin${NC}"
    echo ""
    echo -e "  ${CYAN}Useful Commands:${NC}"
    echo -e "  → Status:  ${YELLOW}systemctl status olt-backend${NC}"
    echo -e "  → Logs:    ${YELLOW}journalctl -u olt-backend -f${NC}"
    echo -e "  → Restart: ${YELLOW}systemctl restart olt-backend${NC}"
    echo ""
    echo -e "  ${CYAN}Installation Directory:${NC} $INSTALL_DIR"
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

    echo ""
    print_status "Starting installation..."
    echo ""

    install_dependencies
    install_nodejs
    setup_repository
    setup_backend
    setup_frontend
    setup_nginx
    setup_service
    setup_firewall

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
