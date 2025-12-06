#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║      OLT Manager License Server - Installation Script         ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Run on your public IP server to set up license management
# Usage: sudo bash install_license_server.sh
#

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║      OLT Manager License Server - Setup                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo bash install_license_server.sh"
    exit 1
fi

# Get admin credentials
echo "Set your admin login credentials:"
read -p "Admin Username [admin]: " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

read -s -p "Admin Password [auto-generate]: " ADMIN_PASS
echo ""
if [ -z "$ADMIN_PASS" ]; then
    ADMIN_PASS=$(openssl rand -base64 12)
    echo "Generated password: $ADMIN_PASS"
fi

# Generate secret key for sessions
FLASK_SECRET=$(openssl rand -hex 32)

echo ""
echo "📦 Installing dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip nginx > /dev/null 2>&1
pip3 install flask flask-cors gunicorn > /dev/null 2>&1
echo "✓ Dependencies installed"

# Create directory
INSTALL_DIR="/opt/license-server"
mkdir -p $INSTALL_DIR

# Copy files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/license_server.py" $INSTALL_DIR/
chmod +x $INSTALL_DIR/license_server.py
echo "✓ Files copied"

# Create systemd service
cat > /etc/systemd/system/license-server.service << EOF
[Unit]
Description=OLT Manager License Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/license-server
Environment=ADMIN_USER=$ADMIN_USER
Environment=ADMIN_PASS=$ADMIN_PASS
Environment=FLASK_SECRET=$FLASK_SECRET
ExecStart=/usr/local/bin/gunicorn -w 2 -b 127.0.0.1:5000 license_server:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Service created"

# Configure nginx
cat > /etc/nginx/sites-available/license-server << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/license-server /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
echo "✓ Nginx configured"

# Start services
systemctl daemon-reload
systemctl enable license-server > /dev/null 2>&1
systemctl start license-server
systemctl restart nginx

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           License Server Installed!                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  🌐 Dashboard URL: http://$SERVER_IP"
echo ""
echo "  👤 Login Credentials:"
echo "     Username: $ADMIN_USER"
echo "     Password: $ADMIN_PASS"
echo ""
echo "  ⚠️  SAVE THESE CREDENTIALS!"
echo ""
echo "  Commands:"
echo "    Status:  systemctl status license-server"
echo "    Logs:    journalctl -u license-server -f"
echo "    Restart: systemctl restart license-server"
echo ""
echo "  For SSL (recommended):"
echo "    apt install certbot python3-certbot-nginx"
echo "    certbot --nginx -d yourdomain.com"
echo ""
