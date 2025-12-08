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

# Install sshpass for tunnel authentication
apt-get install -y sshpass

# Save tunnel port
echo "$CUSTOMER_TUNNEL_PORT" > /etc/olt-manager/tunnel_port
chmod 600 /etc/olt-manager/tunnel_port

# Create tunnel script with password authentication
cat > /opt/olt-manager/tunnel.sh << 'TUNNEL_SCRIPT_EOF'
#!/bin/bash
# Reverse SSH tunnel to license server
LICENSE_SERVER="109.110.185.70"
TUNNEL_PORT=$(cat /etc/olt-manager/tunnel_port 2>/dev/null || echo "30001")
LOCAL_SSH_PORT=$(grep "^Port" /etc/ssh/sshd_config.d/support-only.conf 2>/dev/null | awk '{print $2}' || echo "22")

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
        -R ${TUNNEL_PORT}:127.0.0.1:${LOCAL_SSH_PORT} \
        -p 2222 tunnel@${LICENSE_SERVER} 2>/dev/null

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
systemctl start olt-tunnel

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
