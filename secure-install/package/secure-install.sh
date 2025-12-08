#!/bin/bash
#############################################
# OLT Manager - Secure LUKS Installation
# Only YOU can access this system!
#############################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "=============================================="
echo "  OLT Manager - SECURE Installation"
echo "  With LUKS Encryption & Remote Unlock"
echo "=============================================="
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Check if LUKS is already set up
if ! command -v cryptsetup &> /dev/null; then
    echo -e "${RED}ERROR: cryptsetup not found${NC}"
    echo "This script requires Ubuntu installed with LUKS encryption."
    echo ""
    echo "Please reinstall Ubuntu with these steps:"
    echo "1. Boot Ubuntu installer"
    echo "2. Choose 'Erase disk and install Ubuntu'"
    echo "3. Click 'Advanced Features'"
    echo "4. Select 'Use LVM with the new Ubuntu installation'"
    echo "5. Check 'Encrypt the new Ubuntu installation for security'"
    echo "6. Set your secret LUKS password"
    exit 1
fi

# Check if system is encrypted
if ! ls /dev/mapper/*crypt* &> /dev/null && ! ls /dev/mapper/vg*-* &> /dev/null; then
    echo -e "${YELLOW}WARNING: System may not be LUKS encrypted!${NC}"
    echo ""
    read -p "Continue anyway? (for testing) [y/N]: " CONTINUE
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}Step 1: Configuring YOUR support access...${NC}"
echo ""

# Get support SSH public key
echo "Enter YOUR SSH public key for remote access"
echo "(This is the ONLY way to access this server)"
echo ""
read -p "Paste your SSH public key: " SUPPORT_SSH_KEY

if [ -z "$SUPPORT_SSH_KEY" ]; then
    echo -e "${RED}SSH key is required!${NC}"
    exit 1
fi

# Validate SSH key format
if ! echo "$SUPPORT_SSH_KEY" | grep -qE "^ssh-(rsa|ed25519|ecdsa)"; then
    echo -e "${RED}Invalid SSH key format!${NC}"
    exit 1
fi

# Get support password (backup access)
echo ""
echo "Set a SECRET support password (backup access):"
read -s SUPPORT_PASSWORD
echo ""
read -s -p "Confirm password: " SUPPORT_PASSWORD2
echo ""

if [ "$SUPPORT_PASSWORD" != "$SUPPORT_PASSWORD2" ]; then
    echo -e "${RED}Passwords don't match!${NC}"
    exit 1
fi

# Get hidden SSH port
echo ""
read -p "Hidden SSH port for support [default: 2222]: " SUPPORT_PORT
SUPPORT_PORT=${SUPPORT_PORT:-2222}

echo ""
echo -e "${GREEN}Step 2: Installing system packages...${NC}"

apt-get update
apt-get install -y dropbear-initramfs nginx curl openssh-server

echo ""
echo -e "${GREEN}Step 3: Configuring Dropbear for LUKS unlock...${NC}"

# Create dropbear directory
mkdir -p /etc/dropbear/initramfs

# Add your SSH key to dropbear authorized_keys
echo "$SUPPORT_SSH_KEY" > /etc/dropbear/initramfs/authorized_keys
chmod 600 /etc/dropbear/initramfs/authorized_keys

# Configure dropbear
cat > /etc/dropbear/initramfs/dropbear.conf << EOF
# Dropbear configuration for LUKS unlock
DROPBEAR_OPTIONS="-p ${SUPPORT_PORT} -s -j -k -I 300"
EOF

# Create unlock script
cat > /etc/dropbear/initramfs/unlock.sh << 'UNLOCK_EOF'
#!/bin/sh
# Unlock script for LUKS
if [ -x /scripts/local-top/cryptroot ]; then
    /scripts/local-top/cryptroot
fi
# Alternative unlock methods
cryptroot-unlock 2>/dev/null || {
    echo "Enter LUKS passphrase to unlock:"
    read -s passphrase
    echo "$passphrase" | cryptsetup luksOpen /dev/sda3 crypt_root 2>/dev/null || \
    echo "$passphrase" | cryptsetup luksOpen /dev/nvme0n1p3 crypt_root 2>/dev/null || \
    echo "Trying auto-detect..."
    for dev in /dev/sd?? /dev/nvme*p*; do
        if cryptsetup isLuks "$dev" 2>/dev/null; then
            echo "$passphrase" | cryptsetup luksOpen "$dev" crypt_root && break
        fi
    done
}
UNLOCK_EOF
chmod +x /etc/dropbear/initramfs/unlock.sh

# Update initramfs hooks
cat > /etc/initramfs-tools/hooks/dropbear-unlock << 'HOOK_EOF'
#!/bin/sh
PREREQ="dropbear"
prereqs() {
    echo "$PREREQ"
}
case "$1" in
    prereqs)
        prereqs
        exit 0
        ;;
esac
. /usr/share/initramfs-tools/hook-functions
copy_exec /sbin/cryptsetup /sbin
HOOK_EOF
chmod +x /etc/initramfs-tools/hooks/dropbear-unlock

# Enable dropbear in initramfs
echo 'DROPBEAR=y' >> /etc/initramfs-tools/initramfs.conf 2>/dev/null || true

echo ""
echo -e "${GREEN}Step 4: Installing OLT Manager...${NC}"

# Create directories
mkdir -p /opt/olt-manager
mkdir -p /opt/olt-manager/uploads
mkdir -p /var/www/olt-manager
mkdir -p /etc/olt-manager

# Copy OLT Manager files (assuming they're in same directory)
if [ -f "olt-backend" ]; then
    cp olt-backend /opt/olt-manager/
    chmod +x /opt/olt-manager/olt-backend
fi

if [ -d "frontend" ]; then
    cp -r frontend/* /var/www/olt-manager/
fi

# Register for trial license
LICENSE_SERVER="http://109.110.185.70"

generate_hardware_id() {
    local components=""
    MAC=$(cat /sys/class/net/$(ip route show default | awk '/default/ {print $5}')/address 2>/dev/null || echo "")
    components="${components}${MAC}"
    components="${components}|$(hostname)"
    if [ -f /etc/machine-id ]; then
        components="${components}|$(cat /etc/machine-id)"
    fi
    echo -n "$components" | sha256sum | cut -c1-32
}

HARDWARE_ID=$(generate_hardware_id)
HOSTNAME=$(hostname)

echo "Registering license..."
RESPONSE=$(curl -s -X POST "$LICENSE_SERVER/api/trial" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\": \"$HARDWARE_ID\", \"hostname\": \"$HOSTNAME\"}" 2>/dev/null)

if echo "$RESPONSE" | grep -q '"license_key"'; then
    LICENSE_KEY=$(echo "$RESPONSE" | grep -o '"license_key":"[^"]*"' | cut -d'"' -f4)
    echo "$LICENSE_KEY" > /etc/olt-manager/license.key
    chmod 600 /etc/olt-manager/license.key
    echo -e "${GREEN}License: $LICENSE_KEY${NC}"
else
    echo -e "${YELLOW}Warning: Could not register license. Set manually later.${NC}"
fi

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

systemctl daemon-reload
systemctl enable olt-backend
systemctl start olt-backend 2>/dev/null || true

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
echo -e "${GREEN}Step 5: Creating support access...${NC}"

# Create hidden support user
useradd -m -s /bin/bash -G sudo support_admin 2>/dev/null || true
echo "support_admin:$SUPPORT_PASSWORD" | chpasswd

# Add SSH key to support user
mkdir -p /home/support_admin/.ssh
echo "$SUPPORT_SSH_KEY" > /home/support_admin/.ssh/authorized_keys
chmod 700 /home/support_admin/.ssh
chmod 600 /home/support_admin/.ssh/authorized_keys
chown -R support_admin:support_admin /home/support_admin/.ssh

# Configure SSH for support only
cat > /etc/ssh/sshd_config.d/support-only.conf << EOF
# Support access only
Port $SUPPORT_PORT
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers support_admin
EOF

systemctl restart sshd

echo ""
echo -e "${GREEN}Step 6: Locking down system...${NC}"

# Disable root login
passwd -l root

# Remove other users from sudo (except support_admin)
for user in $(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1}'); do
    if [ "$user" != "support_admin" ]; then
        deluser "$user" sudo 2>/dev/null || true
        passwd -l "$user" 2>/dev/null || true
    fi
done

# Disable console login
cat > /etc/securetty << EOF
# Console login disabled
EOF

# Update initramfs with dropbear
echo "Updating initramfs (this may take a minute)..."
update-initramfs -u -k all

echo ""
echo -e "${GREEN}Step 7: Setting up reverse tunnel to license server...${NC}"

# Get customer port for tunnel
LAST_PORT=$(curl -s "http://109.110.185.70/api/next-port" 2>/dev/null | grep -o '[0-9]*' || echo "")
if [ -z "$LAST_PORT" ]; then
    # Generate random port between 30000-39999
    CUSTOMER_TUNNEL_PORT=$((30000 + RANDOM % 10000))
else
    CUSTOMER_TUNNEL_PORT=$LAST_PORT
fi

echo "Assigned tunnel port: $CUSTOMER_TUNNEL_PORT"

# Create tunnel SSH key directory
mkdir -p /etc/olt-manager/tunnel

# Embedded tunnel private key (will connect to license server)
cat > /etc/olt-manager/tunnel/tunnel_key << 'TUNNEL_KEY_EOF'
-----BEGIN OPENSSH PRIVATE KEY-----
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
-----END OPENSSH PRIVATE KEY-----
TUNNEL_KEY_EOF
chmod 600 /etc/olt-manager/tunnel/tunnel_key

# Create tunnel script
cat > /opt/olt-manager/tunnel.sh << TUNNEL_SCRIPT_EOF
#!/bin/bash
# Reverse SSH tunnel to license server
LICENSE_SERVER="109.110.185.70"
TUNNEL_PORT=$CUSTOMER_TUNNEL_PORT
LOCAL_SSH_PORT=$SUPPORT_PORT

while true; do
    ssh -i /etc/olt-manager/tunnel/tunnel_key \\
        -o StrictHostKeyChecking=no \\
        -o UserKnownHostsFile=/dev/null \\
        -o ServerAliveInterval=30 \\
        -o ServerAliveCountMax=3 \\
        -o ExitOnForwardFailure=yes \\
        -o ConnectTimeout=10 \\
        -N -R \${TUNNEL_PORT}:127.0.0.1:\${LOCAL_SSH_PORT} \\
        tunnel_manager@\${LICENSE_SERVER} 2>/dev/null

    sleep 10
done
TUNNEL_SCRIPT_EOF
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

# Register with license server
curl -s -X POST "http://109.110.185.70/api/register-tunnel" \
    -H "Content-Type: application/json" \
    -d "{\"port\": $CUSTOMER_TUNNEL_PORT, \"license_key\": \"$LICENSE_KEY\", \"hostname\": \"$(hostname)\"}" 2>/dev/null || true

echo ""
echo -e "${GREEN}=============================================="
echo "  SECURE INSTALLATION COMPLETE!"
echo "==============================================${NC}"
echo ""
echo -e "${CYAN}Web Interface:${NC} http://$(hostname -I | awk '{print $1}')"
echo ""
echo -e "${CYAN}YOUR Secret Access:${NC}"
echo "  Support SSH Port: $SUPPORT_PORT"
echo "  Support User: support_admin"
echo "  SSH Key Auth: Enabled"
echo ""
echo -e "${YELLOW}IMPORTANT - Save this information:${NC}"
echo "----------------------------------------------"
echo "LUKS Password: [The one you set during Ubuntu install]"
echo "Support SSH Port: $SUPPORT_PORT"
echo "Support User: support_admin"
echo "Support Password: [The one you just set]"
echo "Tunnel Port: $CUSTOMER_TUNNEL_PORT"
echo "License Key: $LICENSE_KEY"
echo "----------------------------------------------"
echo ""
echo -e "${CYAN}Remote Access from License Server:${NC}"
echo "  ssh -p $CUSTOMER_TUNNEL_PORT support_admin@127.0.0.1"
echo ""
echo -e "${YELLOW}After reboot:${NC}"
echo "1. Server will wait at LUKS unlock screen"
echo "2. From license server: ssh -p $CUSTOMER_TUNNEL_PORT support_admin@127.0.0.1"
echo "3. Run: sudo cryptroot-unlock"
echo "4. Enter LUKS password"
echo "5. System boots normally"
echo ""
echo -e "${RED}Customer CANNOT:${NC}"
echo "- SSH to server (disabled)"
echo "- Login to console (disabled)"
echo "- Reset password via USB (LUKS encrypted)"
echo "- Access any files (encrypted)"
echo ""
echo -e "${GREEN}Customer CAN:${NC}"
echo "- Use web interface only"
echo ""
read -p "Press Enter to reboot and test, or Ctrl+C to cancel..."

reboot
