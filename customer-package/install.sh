#!/bin/bash
# OLT Manager Installation Script

LICENSE_SERVER="http://lic.proxpanel.com"

echo "================================"
echo "  OLT Manager Installation"
echo "================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

# Generate hardware ID (same method as backend)
generate_hardware_id() {
    local components=""

    # Get MAC address
    MAC=$(cat /sys/class/net/$(ip route show default | awk '/default/ {print $5}')/address 2>/dev/null || echo "")
    components="${components}${MAC}"

    # Get hostname
    components="${components}|$(hostname)"

    # Get machine ID
    if [ -f /etc/machine-id ]; then
        components="${components}|$(cat /etc/machine-id)"
    fi

    # Generate hash
    echo -n "$components" | sha256sum | cut -c1-32
}

echo "Generating hardware fingerprint..."
HARDWARE_ID=$(generate_hardware_id)
HOSTNAME=$(hostname)

echo "Hardware ID: $HARDWARE_ID"
echo ""

# Check for existing license key argument
if [ -n "$1" ]; then
    LICENSE_KEY="$1"
    echo "Using provided license key: $LICENSE_KEY"
else
    echo "Registering for 7-day free trial..."
    echo ""

    # Register for trial
    RESPONSE=$(curl -s -X POST "$LICENSE_SERVER/api/trial" \
        -H "Content-Type: application/json" \
        -d "{\"hardware_id\": \"$HARDWARE_ID\", \"hostname\": \"$HOSTNAME\"}" 2>/dev/null)

    if [ -z "$RESPONSE" ]; then
        echo "ERROR: Cannot connect to license server!"
        echo "Please check your internet connection."
        exit 1
    fi

    # Check if success
    if echo "$RESPONSE" | grep -q '"success"'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        EXPIRES=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4)
        echo "Trial license created!"
        echo "License Key: $LICENSE_KEY"
        echo "Expires: $EXPIRES"
    elif echo "$RESPONSE" | grep -q '"exists"'; then
        LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
        echo "License already exists for this hardware."
        echo "License Key: $LICENSE_KEY"
    else
        ERROR=$(echo "$RESPONSE" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
        echo "ERROR: $ERROR"
        echo ""
        echo "You can also install with an existing license key:"
        echo "  ./install.sh YOUR-LICENSE-KEY"
        exit 1
    fi
fi

echo ""
echo "Installing OLT Manager..."

# Create directories
mkdir -p /opt/olt-manager
mkdir -p /opt/olt-manager/uploads
mkdir -p /var/www/olt-manager
mkdir -p /etc/olt-manager

# Copy files
cp olt-backend /opt/olt-manager/
chmod +x /opt/olt-manager/olt-backend
cp -r frontend/* /var/www/olt-manager/

# Save license key
echo "$LICENSE_KEY" > /etc/olt-manager/license.key
chmod 600 /etc/olt-manager/license.key

# Create systemd service
cat > /etc/systemd/system/olt-backend.service << EOF
[Unit]
Description=OLT Manager Backend API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/olt-manager
Environment=LICENSE_SERVER_URL=$LICENSE_SERVER
ExecStart=/opt/olt-manager/olt-backend
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable olt-backend
systemctl start olt-backend

echo ""
echo "Installing nginx..."
apt-get update -qq
apt-get install -y -qq nginx curl

# Configure nginx
cat > /etc/nginx/sites-available/olt-manager << 'NGINX_EOF'
server {
    listen 80 default_server;
    server_name _;

    root /var/www/olt-manager;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /uploads {
        proxy_pass http://127.0.0.1:8000;
    }
}
NGINX_EOF

ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "Access your OLT Manager at: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "License Key: $LICENSE_KEY"
echo ""
echo "Default login:"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "IMPORTANT: Change your password after first login!"
echo ""
echo "Trial Limits:"
echo "  - 7 days validity"
echo "  - Max 2 OLTs"
echo "  - Max 50 ONUs"
echo ""
echo "To upgrade, contact: support@example.com"
echo ""
