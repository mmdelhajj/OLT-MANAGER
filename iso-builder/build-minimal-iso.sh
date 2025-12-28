#!/bin/bash
#
# OLT Manager Minimal ISO Builder
# Uses debootstrap to create a minimal Ubuntu-based appliance
#

set -e

# Configuration
ISO_NAME="olt-manager-appliance"
VERSION=$(cat /root/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
WORK_DIR="/root/olt-iso-build"
OUTPUT_DIR="/root/olt-manager/iso-builder/output"

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
echo "║       OLT Manager Minimal Appliance ISO Builder              ║"
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
apt-get install -y -qq debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools

# Create work directories
print_status "Creating work directories..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"/{chroot,iso/{boot/grub,casper,isolinux,.disk}}
mkdir -p "$OUTPUT_DIR"

# Bootstrap minimal Ubuntu
print_status "Creating minimal Ubuntu system (this takes a few minutes)..."
debootstrap --arch=amd64 --variant=minbase jammy "$WORK_DIR/chroot" http://archive.ubuntu.com/ubuntu/

# Prepare chroot
print_status "Preparing chroot environment..."
mount --bind /dev "$WORK_DIR/chroot/dev"
mount --bind /proc "$WORK_DIR/chroot/proc"
mount --bind /sys "$WORK_DIR/chroot/sys"
cp /etc/resolv.conf "$WORK_DIR/chroot/etc/resolv.conf"

# Copy OLT Manager files
print_status "Copying OLT Manager files..."
mkdir -p "$WORK_DIR/chroot/opt/olt-manager"
cp -r /root/olt-manager/backend "$WORK_DIR/chroot/opt/olt-manager/"

# Copy console menu
mkdir -p "$WORK_DIR/chroot/usr/local/bin"
cp /root/olt-manager/iso-builder/olt-console.sh "$WORK_DIR/chroot/usr/local/bin/olt-console"
chmod +x "$WORK_DIR/chroot/usr/local/bin/olt-console"

# Create customization script
cat > "$WORK_DIR/chroot/tmp/customize.sh" << 'CUSTOMIZE_SCRIPT'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
export HOME=/root

# Configure apt sources
cat > /etc/apt/sources.list << 'EOF'
deb http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu jammy-security main restricted universe multiverse
EOF

apt-get update -qq

# Install kernel and essential packages
apt-get install -y -qq \
    linux-image-generic \
    linux-headers-generic \
    systemd \
    systemd-sysv \
    sudo \
    locales \
    console-setup \
    keyboard-configuration

# Install required packages
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    snmp \
    snmp-mibs-downloader \
    curl \
    wget \
    net-tools \
    iproute2 \
    iputils-ping \
    openssh-server \
    sshpass \
    dbus \
    network-manager \
    netplan.io

# Configure locale
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8

# Set hostname
echo "olt-manager" > /etc/hostname

# Setup Python virtual environment
cd /opt/olt-manager/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>/dev/null || pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt python-multipart aiofiles requests paramiko pysnmp -q

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
        proxy_read_timeout 300;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

# Create www directory
mkdir -p /var/www/html
echo "<h1>OLT Manager</h1><p>Loading...</p>" > /var/www/html/index.html

# Enable services
systemctl enable olt-manager
systemctl enable nginx
systemctl enable ssh
systemctl enable NetworkManager

# Configure auto-login to console menu
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
Type=idle
EOF

# Set console menu as default for tty1
cat > /root/.bash_profile << 'EOF'
if [[ $(tty) == /dev/tty1 ]]; then
    /usr/local/bin/olt-console
fi
EOF

# Set root password (temporary, will be changed on first boot)
echo "root:oltmanager" | chpasswd

# Create first boot script
cat > /opt/olt-manager/firstboot.sh << 'FIRSTBOOT'
#!/bin/bash
mkdir -p /etc/olt-manager

# Generate hardware ID
MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "unknown")
MAC=$(ip link show 2>/dev/null | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':')
FINGERPRINT="${MACHINE_ID}${MAC}"
HASH=$(echo -n "$FINGERPRINT" | md5sum | cut -d' ' -f1)
HARDWARE_ID="OLT-${HASH:0:8}-${HASH:8:8}-${HASH:16:8}"
echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id

# Register trial
curl -s -X POST "http://lic.proxpanel.com/api/register-trial" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}" > /dev/null 2>&1

# Register tunnel
RESPONSE=$(curl -s -X POST "http://lic.proxpanel.com/api/tunnel/register" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}" 2>/dev/null)

TUNNEL_PORT=$(echo "$RESPONSE" | grep -o '"port":[0-9]*' | cut -d':' -f2)
if [[ -n "$TUNNEL_PORT" ]]; then
    cat > /opt/olt-manager/tunnel.sh << EOF
#!/bin/bash
export SSHPASS="yo3nFHoe5TXNcEDdTV85"
exec sshpass -e ssh -N -R ${TUNNEL_PORT}:localhost:22 -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -p 2222 tunnel@lic.proxpanel.com
EOF
    chmod +x /opt/olt-manager/tunnel.sh
    systemctl enable olt-tunnel 2>/dev/null
    systemctl start olt-tunnel 2>/dev/null
fi

touch /etc/olt-manager/.firstboot_done
FIRSTBOOT
chmod +x /opt/olt-manager/firstboot.sh

# Create first boot service
cat > /etc/systemd/system/olt-firstboot.service << 'EOF'
[Unit]
Description=OLT Manager First Boot
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
systemctl enable olt-firstboot

# Create tunnel service
cat > /etc/systemd/system/olt-tunnel.service << 'EOF'
[Unit]
Description=OLT Manager Remote Tunnel
After=network-online.target
Wants=network-online.target
ConditionPathExists=/opt/olt-manager/tunnel.sh

[Service]
Type=simple
ExecStart=/opt/olt-manager/tunnel.sh
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

echo "Customization complete!"
CUSTOMIZE_SCRIPT

chmod +x "$WORK_DIR/chroot/tmp/customize.sh"

# Run customization in chroot
print_status "Running customization (this may take 10-15 minutes)..."
chroot "$WORK_DIR/chroot" /bin/bash /tmp/customize.sh

# Cleanup chroot
print_status "Cleaning up chroot..."
rm -f "$WORK_DIR/chroot/tmp/customize.sh"
rm -f "$WORK_DIR/chroot/etc/resolv.conf"
umount "$WORK_DIR/chroot/sys" 2>/dev/null || true
umount "$WORK_DIR/chroot/proc" 2>/dev/null || true
umount "$WORK_DIR/chroot/dev" 2>/dev/null || true

# Copy kernel and initrd
print_status "Preparing boot files..."
cp "$WORK_DIR/chroot/boot/vmlinuz-"* "$WORK_DIR/iso/casper/vmlinuz"
cp "$WORK_DIR/chroot/boot/initrd.img-"* "$WORK_DIR/iso/casper/initrd"

# Create squashfs
print_status "Creating squashfs filesystem (this takes a few minutes)..."
mksquashfs "$WORK_DIR/chroot" "$WORK_DIR/iso/casper/filesystem.squashfs" -comp xz -b 1M -Xdict-size 100%

# Create filesystem.size
du -sx --block-size=1 "$WORK_DIR/chroot" | cut -f1 > "$WORK_DIR/iso/casper/filesystem.size"

# Create GRUB configuration
cat > "$WORK_DIR/iso/boot/grub/grub.cfg" << 'EOF'
set timeout=5
set default=0

menuentry "OLT Manager Appliance - Install" {
    linux /casper/vmlinuz boot=casper quiet splash ---
    initrd /casper/initrd
}

menuentry "OLT Manager Appliance - Install (Safe Mode)" {
    linux /casper/vmlinuz boot=casper quiet splash nomodeset ---
    initrd /casper/initrd
}
EOF

# Create disk info
echo "OLT Manager Appliance $VERSION" > "$WORK_DIR/iso/.disk/info"
touch "$WORK_DIR/iso/.disk/base_installable"

# Create ISO
print_status "Creating ISO image..."
ISO_FILE="$OUTPUT_DIR/${ISO_NAME}-${VERSION}.iso"

grub-mkrescue -o "$ISO_FILE" "$WORK_DIR/iso" 2>/dev/null || {
    print_warning "grub-mkrescue failed, trying xorriso..."
    xorriso -as mkisofs \
        -r -V "OLT-MANAGER" \
        -J -joliet-long \
        -o "$ISO_FILE" \
        "$WORK_DIR/iso"
}

# Cleanup
print_status "Cleaning up..."
rm -rf "$WORK_DIR"

# Show result
if [[ -f "$ISO_FILE" ]]; then
    ISO_SIZE=$(du -h "$ISO_FILE" | cut -f1)
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    ISO Build Complete!                       ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  File: $ISO_FILE"
    echo "║  Size: $ISO_SIZE"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
else
    print_error "ISO creation failed!"
    exit 1
fi
