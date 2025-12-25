#!/bin/bash
# ============================================
# OLT Manager - Easy Installer (Protected)
# Just run: curl -s URL | bash
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════╗"
echo "║        OLT MANAGER - INSTALLATION             ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

INSTALL_DIR="/opt/olt-manager"
DOWNLOAD_URL="https://github.com/mmdelhajj/OLT-MANAGER/raw/main/olt-manager-compiled-20251225.tar.gz"

echo -e "${YELLOW}[1/7] Installing dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq nginx wget curl > /dev/null 2>&1
echo -e "${GREEN}  ✓ Dependencies installed${NC}"

echo -e "${YELLOW}[2/7] Downloading OLT Manager...${NC}"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR
wget -q "$DOWNLOAD_URL" -O olt-manager.tar.gz
tar -xzf olt-manager.tar.gz
rm olt-manager.tar.gz
chmod +x olt-manager
echo -e "${GREEN}  ✓ Downloaded and extracted${NC}"

echo -e "${YELLOW}[3/7] Creating directories...${NC}"
mkdir -p /etc/olt-manager
mkdir -p $INSTALL_DIR/data
mkdir -p $INSTALL_DIR/uploads
echo -e "${GREEN}  ✓ Directories created${NC}"

echo -e "${YELLOW}[4/7] Setting up systemd service...${NC}"
cat > /etc/systemd/system/olt-manager.service << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/olt-manager
ExecStart=/opt/olt-manager/olt-manager
Restart=always
RestartSec=5
Environment=OLT_LICENSE_KEY=

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable olt-manager > /dev/null 2>&1
systemctl start olt-manager
echo -e "${GREEN}  ✓ Service created and started${NC}"

echo -e "${YELLOW}[5/7] Configuring nginx...${NC}"
cat > /etc/nginx/sites-available/olt-manager << 'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/
nginx -t > /dev/null 2>&1
systemctl restart nginx
echo -e "${GREEN}  ✓ Nginx configured${NC}"

echo -e "${YELLOW}[6/7] Opening firewall...${NC}"
ufw allow 80/tcp > /dev/null 2>&1 || true
ufw allow 22/tcp > /dev/null 2>&1 || true
iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
echo -e "${GREEN}  ✓ Firewall configured${NC}"

echo -e "${YELLOW}[7/7] Getting system info...${NC}"
sleep 3
HARDWARE_ID=$(grep -o 'OLT-[A-Z0-9-]*' /var/log/syslog 2>/dev/null | tail -1 || journalctl -u olt-manager --no-pager | grep -o 'OLT-[A-Z0-9-]*' | tail -1)
IP_ADDR=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}  ✓ System info collected${NC}"

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗"
echo -e "║         INSTALLATION COMPLETE!                ║"
echo -e "╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Access:${NC}      http://$IP_ADDR"
echo -e "  ${BLUE}Username:${NC}   admin"
echo -e "  ${BLUE}Password:${NC}   admin"
echo ""
echo -e "  ${YELLOW}Hardware ID:${NC} $HARDWARE_ID"
echo ""
echo -e "  ${YELLOW}To activate license:${NC}"
echo -e "  echo 'YOUR_LICENSE_KEY' > /etc/olt-manager/license.key"
echo -e "  systemctl restart olt-manager"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
