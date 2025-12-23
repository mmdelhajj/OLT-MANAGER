#!/bin/bash
#
# OLT Manager Appliance ISO Builder
# Creates a custom Ubuntu-based ISO with OLT Manager pre-installed
#

set -e

# Configuration
ISO_NAME="olt-manager-appliance"
VERSION=$(cat /root/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
WORK_DIR="/tmp/olt-iso-build"
OUTPUT_DIR="/root/olt-manager/iso-builder/output"
UBUNTU_ISO_URL="https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso"
UBUNTU_ISO="/tmp/ubuntu-22.04-server.iso"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[X]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          OLT Manager Appliance ISO Builder                   ║"
echo "║                    Version $VERSION                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

# Install required tools
print_status "Installing required tools..."
apt-get update -qq
apt-get install -y -qq xorriso squashfs-tools genisoimage wget p7zip-full

# Create work directories
print_status "Creating work directories..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"/{iso,squashfs,custom}
mkdir -p "$OUTPUT_DIR"

# Download Ubuntu ISO if not exists
if [[ ! -f "$UBUNTU_ISO" ]]; then
    print_status "Downloading Ubuntu Server ISO..."
    wget -q --show-progress -O "$UBUNTU_ISO" "$UBUNTU_ISO_URL"
fi

# Extract ISO
print_status "Extracting Ubuntu ISO..."
7z x -o"$WORK_DIR/iso" "$UBUNTU_ISO" -y > /dev/null

# Extract squashfs
print_status "Extracting squashfs filesystem..."
unsquashfs -d "$WORK_DIR/squashfs" "$WORK_DIR/iso/casper/ubuntu-server-minimal.squashfs"

# Prepare chroot environment
print_status "Preparing chroot environment..."
mount --bind /dev "$WORK_DIR/squashfs/dev"
mount --bind /proc "$WORK_DIR/squashfs/proc"
mount --bind /sys "$WORK_DIR/squashfs/sys"
mount --bind /run "$WORK_DIR/squashfs/run"
cp /etc/resolv.conf "$WORK_DIR/squashfs/etc/resolv.conf"

# Copy OLT Manager files
print_status "Copying OLT Manager files..."
mkdir -p "$WORK_DIR/squashfs/opt/olt-manager"
cp -r /root/olt-manager/backend "$WORK_DIR/squashfs/opt/olt-manager/"
cp -r /root/olt-manager/frontend "$WORK_DIR/squashfs/opt/olt-manager/" 2>/dev/null || true

# Copy console menu
mkdir -p "$WORK_DIR/squashfs/usr/local/bin"
cp /root/olt-manager/iso-builder/olt-console.sh "$WORK_DIR/squashfs/usr/local/bin/olt-console"
chmod +x "$WORK_DIR/squashfs/usr/local/bin/olt-console"

# Create customization script
cat > "$WORK_DIR/squashfs/tmp/customize.sh" << 'CUSTOMIZE_SCRIPT'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

# Update system
apt-get update -qq
apt-get upgrade -y -qq

# Install required packages
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nginx \
    snmp snmp-mibs-downloader \
    curl wget \
    net-tools \
    openssh-server \
    sshpass \
    autossh

# Setup Python virtual environment
cd /opt/olt-manager/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create OLT Manager service
cat > /etc/systemd/system/olt-manager.service << 'EOF'
[Unit]
Description=OLT Manager Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/olt-manager/backend
Environment=PATH=/opt/olt-manager/backend/venv/bin:/usr/bin:/bin
ExecStart=/opt/olt-manager/backend/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
cat > /etc/nginx/sites-available/olt-manager << 'EOF'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 50M;

    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

# Enable services
systemctl enable olt-manager
systemctl enable nginx

# Create appliance user (no shell access)
useradd -r -s /usr/sbin/nologin appliance 2>/dev/null || true

# Configure auto-login to console menu
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF

# Set console menu as shell for tty1
cat > /root/.bash_profile << 'EOF'
# If on tty1, run console menu
if [[ $(tty) == /dev/tty1 ]]; then
    /usr/local/bin/olt-console
fi
EOF

# Disable SSH password auth (only tunnel allowed)
cat >> /etc/ssh/sshd_config << 'EOF'

# OLT Manager Appliance - Restrict SSH
PasswordAuthentication no
PermitRootLogin no
AllowUsers tunnel
EOF

# Create tunnel service for remote management
cat > /etc/systemd/system/olt-tunnel.service << 'EOF'
[Unit]
Description=OLT Manager Remote Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/opt/olt-manager/tunnel.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create tunnel script placeholder (will be configured on first boot)
cat > /opt/olt-manager/tunnel.sh << 'EOF'
#!/bin/bash
# Tunnel script - configured on first boot
sleep infinity
EOF
chmod +x /opt/olt-manager/tunnel.sh

# Generate hardware ID on first boot
cat > /etc/systemd/system/olt-firstboot.service << 'EOF'
[Unit]
Description=OLT Manager First Boot Setup
After=network-online.target
Wants=network-online.target
ConditionPathExists=!/etc/olt-manager/.firstboot_done

[Service]
Type=oneshot
ExecStart=/opt/olt-manager/firstboot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Create first boot script
cat > /opt/olt-manager/firstboot.sh << 'FIRSTBOOT'
#!/bin/bash
# Generate hardware ID
mkdir -p /etc/olt-manager

MACHINE_ID=$(cat /etc/machine-id)
CPU_INFO=$(cat /proc/cpuinfo | grep -m1 "model name" | md5sum | cut -d' ' -f1)
MAC=$(ip link show | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':')

FINGERPRINT="${MACHINE_ID}${CPU_INFO}${MAC}"
HASH=$(echo -n "$FINGERPRINT" | md5sum | cut -d' ' -f1)
HARDWARE_ID="OLT-${HASH:0:8}-${HASH:8:8}-${HASH:16:8}"

echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id
chmod 600 /etc/olt-manager/hardware.id

# Register trial license
curl -s -X POST "http://lic.proxpanel.com/api/register-trial" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}" > /dev/null 2>&1

# Get tunnel port and configure tunnel
RESPONSE=$(curl -s -X POST "http://lic.proxpanel.com/api/tunnel/register" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}")

TUNNEL_PORT=$(echo "$RESPONSE" | grep -o '"port":[0-9]*' | cut -d':' -f2)

if [[ -n "$TUNNEL_PORT" ]]; then
    cat > /opt/olt-manager/tunnel.sh << EOF
#!/bin/bash
export SSHPASS="yo3nFHoe5TXNcEDdTV85"
exec sshpass -e ssh -N \\
    -R ${TUNNEL_PORT}:localhost:22 \\
    -o StrictHostKeyChecking=no \\
    -o ServerAliveInterval=60 \\
    -o ServerAliveCountMax=3 \\
    -o ExitOnForwardFailure=yes \\
    -p 2222 tunnel@lic.proxpanel.com
EOF
    chmod +x /opt/olt-manager/tunnel.sh
    systemctl enable olt-tunnel
    systemctl start olt-tunnel
fi

# Mark first boot done
touch /etc/olt-manager/.firstboot_done
FIRSTBOOT
chmod +x /opt/olt-manager/firstboot.sh

systemctl enable olt-firstboot

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -rf /tmp/*

echo "Customization complete!"
CUSTOMIZE_SCRIPT

chmod +x "$WORK_DIR/squashfs/tmp/customize.sh"

# Run customization in chroot
print_status "Running customization (this may take a while)..."
chroot "$WORK_DIR/squashfs" /tmp/customize.sh

# Cleanup chroot
print_status "Cleaning up chroot..."
rm -f "$WORK_DIR/squashfs/tmp/customize.sh"
umount "$WORK_DIR/squashfs/run" 2>/dev/null || true
umount "$WORK_DIR/squashfs/sys" 2>/dev/null || true
umount "$WORK_DIR/squashfs/proc" 2>/dev/null || true
umount "$WORK_DIR/squashfs/dev" 2>/dev/null || true

# Repack squashfs
print_status "Repacking squashfs filesystem..."
rm -f "$WORK_DIR/iso/casper/ubuntu-server-minimal.squashfs"
mksquashfs "$WORK_DIR/squashfs" "$WORK_DIR/iso/casper/ubuntu-server-minimal.squashfs" -comp xz -b 1M

# Update ISO boot configuration
print_status "Updating boot configuration..."
cat > "$WORK_DIR/iso/boot/grub/grub.cfg" << 'EOF'
set timeout=5
set default=0

menuentry "Install OLT Manager Appliance" {
    linux /casper/vmlinuz quiet autoinstall ---
    initrd /casper/initrd
}

menuentry "Install OLT Manager Appliance (Safe Mode)" {
    linux /casper/vmlinuz quiet autoinstall nomodeset ---
    initrd /casper/initrd
}
EOF

# Create ISO
print_status "Creating ISO image..."
ISO_FILE="$OUTPUT_DIR/${ISO_NAME}-${VERSION}.iso"

xorriso -as mkisofs \
    -r -V "OLT-MANAGER-$VERSION" \
    -o "$ISO_FILE" \
    -J -joliet-long \
    -b boot/grub/i386-pc/eltorito.img \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    --grub2-boot-info \
    --grub2-mbr /usr/lib/grub/i386-pc/boot_hybrid.img \
    -append_partition 2 0xef boot/grub/efi.img \
    -appended_part_as_gpt \
    -eltorito-alt-boot \
    -e --interval:appended_partition_2:all:: \
    -no-emul-boot \
    "$WORK_DIR/iso" 2>/dev/null || {
        # Fallback to simpler ISO creation
        genisoimage -r -V "OLT-MANAGER-$VERSION" \
            -cache-inodes -J -l \
            -b isolinux/isolinux.bin \
            -c isolinux/boot.cat \
            -no-emul-boot \
            -boot-load-size 4 \
            -boot-info-table \
            -o "$ISO_FILE" \
            "$WORK_DIR/iso" 2>/dev/null
    }

# Cleanup
print_status "Cleaning up..."
rm -rf "$WORK_DIR"

# Show result
ISO_SIZE=$(du -h "$ISO_FILE" | cut -f1)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    ISO Build Complete!                       ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  ISO File: $ISO_FILE"
echo "║  Size: $ISO_SIZE"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
print_status "You can now distribute this ISO to customers."
