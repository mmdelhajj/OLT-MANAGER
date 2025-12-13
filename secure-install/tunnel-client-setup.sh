#!/bin/bash
#############################################
# Customer Server - Reverse Tunnel Setup
# Creates permanent tunnel to your license server
#############################################

LICENSE_SERVER="lic.proxpanel.com"
TUNNEL_USER="tunnel_manager"

# This will be set during installation
CUSTOMER_PORT="$1"
TUNNEL_KEY="$2"

if [ -z "$CUSTOMER_PORT" ]; then
    echo "Usage: $0 <customer_port> [tunnel_private_key_file]"
    echo "Example: $0 30001 /path/to/tunnel_key"
    exit 1
fi

echo "Setting up reverse tunnel on port $CUSTOMER_PORT..."

# Create tunnel user
useradd -r -s /bin/false tunnel_client 2>/dev/null || true

# Setup SSH key for tunnel
mkdir -p /etc/olt-manager/tunnel
if [ -n "$TUNNEL_KEY" ] && [ -f "$TUNNEL_KEY" ]; then
    cp "$TUNNEL_KEY" /etc/olt-manager/tunnel/tunnel_key
else
    # Use embedded key (will be set during package creation)
    cat > /etc/olt-manager/tunnel/tunnel_key << 'KEYEOF'
TUNNEL_PRIVATE_KEY_PLACEHOLDER
KEYEOF
fi
chmod 600 /etc/olt-manager/tunnel/tunnel_key

# Create tunnel script
cat > /opt/olt-manager/tunnel.sh << EOF
#!/bin/bash
# Reverse SSH tunnel to license server
while true; do
    ssh -i /etc/olt-manager/tunnel/tunnel_key \\
        -o StrictHostKeyChecking=no \\
        -o ServerAliveInterval=30 \\
        -o ServerAliveCountMax=3 \\
        -o ExitOnForwardFailure=yes \\
        -N -R ${CUSTOMER_PORT}:127.0.0.1:2222 \\
        ${TUNNEL_USER}@${LICENSE_SERVER}

    echo "Tunnel disconnected, reconnecting in 10 seconds..."
    sleep 10
done
EOF
chmod +x /opt/olt-manager/tunnel.sh

# Create systemd service for tunnel
cat > /etc/systemd/system/olt-tunnel.service << EOF
[Unit]
Description=OLT Manager Reverse Tunnel
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
systemctl enable olt-tunnel
systemctl start olt-tunnel

echo ""
echo "Tunnel configured!"
echo "Your server is accessible from license server on port $CUSTOMER_PORT"
echo ""
echo "To connect from license server:"
echo "  ssh -p $CUSTOMER_PORT support_admin@127.0.0.1"
