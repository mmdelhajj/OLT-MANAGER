#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║           OLT Manager - Installation Script                   ║
# ║           Version 1.0                                          ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Usage: sudo bash install.sh YOUR-LICENSE-KEY
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           OLT Manager - Installation                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run as root: sudo bash install.sh LICENSE-KEY${NC}"
    exit 1
fi

# Get license key from argument or prompt
LICENSE_KEY="$1"
if [ -z "$LICENSE_KEY" ]; then
    echo -e "${YELLOW}Enter your license key:${NC}"
    read -p "> " LICENSE_KEY
fi

if [ -z "$LICENSE_KEY" ]; then
    echo -e "${RED}❌ License key is required${NC}"
    exit 1
fi

# Directories
INSTALL_DIR="/opt/olt-manager"
WEB_DIR="/var/www/olt-manager"
DATA_DIR="/var/lib/olt-manager"
CONFIG_DIR="/etc/olt-manager"

echo -e "${GREEN}📦 Installing OLT Manager...${NC}"
echo ""

# Step 1: Install dependencies
echo "1/6 Installing dependencies..."
apt-get update -qq
apt-get install -y -qq nginx sqlite3 > /dev/null 2>&1
echo -e "    ${GREEN}✓${NC} Dependencies installed"

# Step 2: Create directories
echo "2/6 Creating directories..."
mkdir -p $INSTALL_DIR
mkdir -p $WEB_DIR
mkdir -p $DATA_DIR
mkdir -p $CONFIG_DIR
echo -e "    ${GREEN}✓${NC} Directories created"

# Step 3: Copy files
echo "3/6 Copying files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/olt-manager-backend" $INSTALL_DIR/
chmod +x $INSTALL_DIR/olt-manager-backend
cp -r "$SCRIPT_DIR/frontend/"* $WEB_DIR/
echo -e "    ${GREEN}✓${NC} Files copied"

# Step 4: Save license
echo "4/6 Configuring license..."
echo "$LICENSE_KEY" > $CONFIG_DIR/license.key
chmod 600 $CONFIG_DIR/license.key
echo -e "    ${GREEN}✓${NC} License configured"

# Step 5: Create systemd service
echo "5/6 Creating service..."
cat > /etc/systemd/system/olt-manager.service << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/lib/olt-manager
Environment=LICENSE_SERVER_URL=http://109.110.185.70
ExecStart=/opt/olt-manager/olt-manager-backend
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
echo -e "    ${GREEN}✓${NC} Service created"

# Step 6: Configure nginx
echo "6/6 Configuring web server..."
cat > /etc/nginx/sites-available/olt-manager << 'NGINX'
server {
    listen 80;
    server_name _;

    root /var/www/olt-manager;
    index index.html;

    # Frontend
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
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Uploads
    location /uploads {
        alias /var/lib/olt-manager/uploads;
    }
}
NGINX

# Enable site
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
echo -e "    ${GREEN}✓${NC} Web server configured"

# Start services
echo ""
echo "Starting services..."
systemctl daemon-reload
systemctl enable olt-manager > /dev/null 2>&1
systemctl start olt-manager
systemctl restart nginx

# Wait for backend to start
sleep 3

# Check if running
if systemctl is-active --quiet olt-manager; then
    echo -e "${GREEN}✓ Backend service running${NC}"
else
    echo -e "${RED}✗ Backend service failed to start${NC}"
    echo "  Check logs: journalctl -u olt-manager -f"
fi

if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Web server running${NC}"
else
    echo -e "${RED}✗ Web server failed to start${NC}"
fi

# Get IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Installation Complete!                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${GREEN}🌐 Web Interface:${NC} http://$SERVER_IP"
echo ""
echo -e "  ${GREEN}👤 Default Login:${NC}"
echo "     Username: admin"
echo "     Password: admin123"
echo ""
echo -e "  ${YELLOW}⚠️  Please change the default password after first login!${NC}"
echo ""
echo "  Commands:"
echo "    Status:  systemctl status olt-manager"
echo "    Logs:    journalctl -u olt-manager -f"
echo "    Restart: systemctl restart olt-manager"
echo ""
