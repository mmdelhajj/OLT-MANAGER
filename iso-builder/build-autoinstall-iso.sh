#!/bin/bash
#
# OLT Manager Auto-Install ISO Builder
# Downloads Ubuntu Server ISO and adds autoinstall configuration
#

set -e

VERSION=$(cat /root/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
WORK_DIR="/root/olt-iso-work"
OUTPUT_DIR="/root/olt-manager/iso-builder/output"
ISO_NAME="olt-manager-${VERSION}"

# Ubuntu 22.04 Live Server ISO (smaller than desktop)
UBUNTU_ISO_URL="https://releases.ubuntu.com/22.04.3/ubuntu-22.04.3-live-server-amd64.iso"
UBUNTU_ISO="/root/ubuntu-22.04-server.iso"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[X]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       OLT Manager Auto-Install ISO Builder                   ║"
echo "║                    Version $VERSION                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Cleanup any previous build
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"/{iso-extract,iso-new}
mkdir -p "$OUTPUT_DIR"

# Download Ubuntu ISO if needed
if [[ ! -f "$UBUNTU_ISO" ]] || [[ $(stat -c%s "$UBUNTU_ISO" 2>/dev/null || echo 0) -lt 1000000000 ]]; then
    print_status "Downloading Ubuntu Server ISO (~2GB)..."
    rm -f "$UBUNTU_ISO"
    wget --progress=bar:force -O "$UBUNTU_ISO" "$UBUNTU_ISO_URL"
fi

# Extract ISO
print_status "Extracting Ubuntu ISO..."
7z x -o"$WORK_DIR/iso-extract" "$UBUNTU_ISO" -y > /dev/null 2>&1 || {
    # Fallback to xorriso
    xorriso -osirrox on -indev "$UBUNTU_ISO" -extract / "$WORK_DIR/iso-extract" 2>/dev/null
}

# Copy extracted files
print_status "Preparing custom ISO..."
cp -rT "$WORK_DIR/iso-extract" "$WORK_DIR/iso-new"

# Make writable
chmod -R u+w "$WORK_DIR/iso-new"

# Create autoinstall directory
mkdir -p "$WORK_DIR/iso-new/autoinstall"

# Create the installer package tarball
print_status "Creating installer package..."
INSTALLER_TAR="$WORK_DIR/iso-new/autoinstall/olt-manager.tar.gz"

# Create temp directory for package
PACKAGE_DIR=$(mktemp -d)
mkdir -p "$PACKAGE_DIR/olt-manager"/{backend,scripts}

# Copy backend (excluding unnecessary files)
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='data' --exclude='build' --exclude='dist' \
    /root/olt-manager/backend/ "$PACKAGE_DIR/olt-manager/backend/"

# Copy console script
cp /root/olt-manager/iso-builder/olt-console.sh "$PACKAGE_DIR/olt-manager/scripts/"

# Copy frontend if exists
if [[ -d /var/www/html ]] && [[ -f /var/www/html/index.html ]]; then
    mkdir -p "$PACKAGE_DIR/olt-manager/frontend"
    cp -r /var/www/html/* "$PACKAGE_DIR/olt-manager/frontend/"
fi

# Create tarball
tar -czf "$INSTALLER_TAR" -C "$PACKAGE_DIR" olt-manager
rm -rf "$PACKAGE_DIR"

# Create autoinstall user-data (cloud-init format)
print_status "Creating autoinstall configuration..."
cat > "$WORK_DIR/iso-new/autoinstall/user-data" << 'USERDATA'
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  identity:
    hostname: olt-manager
    username: root
    password: "$6$rounds=4096$randomsalt$hashedpassword"
  ssh:
    install-server: true
    allow-pw: true
  storage:
    layout:
      name: lvm
  late-commands:
    - curtin in-target --target=/target -- bash -c 'echo "root:oltmanager" | chpasswd'
    - curtin in-target --target=/target -- mkdir -p /opt/olt-manager
    - cp /cdrom/autoinstall/olt-manager.tar.gz /target/opt/
    - curtin in-target --target=/target -- tar -xzf /opt/olt-manager.tar.gz -C /opt/
    - curtin in-target --target=/target -- rm /opt/olt-manager.tar.gz
    - cp /cdrom/autoinstall/setup-olt.sh /target/opt/olt-manager/
    - curtin in-target --target=/target -- chmod +x /opt/olt-manager/setup-olt.sh
    - curtin in-target --target=/target -- bash /opt/olt-manager/setup-olt.sh
USERDATA

# Create setup script that runs during installation
cat > "$WORK_DIR/iso-new/autoinstall/setup-olt.sh" << 'SETUP_SCRIPT'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
export HOME=/root

echo "[*] Installing OLT Manager..."

# Install packages
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nginx snmp snmp-mibs-downloader \
    curl wget net-tools openssh-server sshpass

# Setup Python environment
cd /opt/olt-manager/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>/dev/null || \
    pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt python-multipart aiofiles requests paramiko pysnmp -q

# Install console menu
cp /opt/olt-manager/scripts/olt-console.sh /usr/local/bin/olt-console
chmod +x /usr/local/bin/olt-console

# Install frontend
if [[ -d /opt/olt-manager/frontend ]]; then
    mkdir -p /var/www/html
    cp -r /opt/olt-manager/frontend/* /var/www/html/
else
    mkdir -p /var/www/html
    echo "<h1>OLT Manager</h1>" > /var/www/html/index.html
fi

# Create systemd service
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

# Auto-login console
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
Type=idle
EOF

cat > /root/.bash_profile << 'EOF'
if [[ $(tty) == /dev/tty1 ]]; then
    /usr/local/bin/olt-console
fi
EOF

# First boot script
cat > /opt/olt-manager/firstboot.sh << 'FIRSTBOOT'
#!/bin/bash
mkdir -p /etc/olt-manager
MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "unknown")
MAC=$(ip link show 2>/dev/null | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':')
FINGERPRINT="${MACHINE_ID}${MAC}"
HASH=$(echo -n "$FINGERPRINT" | md5sum | cut -d' ' -f1)
HARDWARE_ID="OLT-${HASH:0:8}-${HASH:8:8}-${HASH:16:8}"
echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id

curl -s -X POST "http://lic.proxpanel.com/api/register-trial" \
    -H "Content-Type: application/json" \
    -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$(hostname)\"}" > /dev/null 2>&1

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

# First boot service
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

# Tunnel service
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

# Enable services
systemctl daemon-reload
systemctl enable olt-manager nginx ssh olt-firstboot

echo "[*] OLT Manager installation complete!"
SETUP_SCRIPT

# Create empty meta-data (required)
touch "$WORK_DIR/iso-new/autoinstall/meta-data"

# Update GRUB to autoinstall
print_status "Updating boot configuration..."

# Modify grub.cfg for autoinstall
if [[ -f "$WORK_DIR/iso-new/boot/grub/grub.cfg" ]]; then
    cat > "$WORK_DIR/iso-new/boot/grub/grub.cfg" << 'GRUB_CFG'
set timeout=5
set default=0

menuentry "Install OLT Manager Appliance (Auto)" {
    set gfxpayload=keep
    linux /casper/vmlinuz autoinstall ds=nocloud\;s=/cdrom/autoinstall/ quiet ---
    initrd /casper/initrd
}

menuentry "Install OLT Manager Appliance (Manual)" {
    set gfxpayload=keep
    linux /casper/vmlinuz quiet ---
    initrd /casper/initrd
}

menuentry "Boot from Hard Disk" {
    exit
}
GRUB_CFG
fi

# Also update isolinux for legacy BIOS boot
if [[ -f "$WORK_DIR/iso-new/isolinux/txt.cfg" ]]; then
    cat > "$WORK_DIR/iso-new/isolinux/txt.cfg" << 'ISOLINUX_CFG'
default autoinstall
label autoinstall
  menu label ^Install OLT Manager Appliance (Auto)
  kernel /casper/vmlinuz
  append initrd=/casper/initrd autoinstall ds=nocloud;s=/cdrom/autoinstall/ quiet ---
label manual
  menu label Install OLT Manager Appliance (^Manual)
  kernel /casper/vmlinuz
  append initrd=/casper/initrd quiet ---
ISOLINUX_CFG
fi

# Create the ISO
print_status "Creating ISO image..."

ISO_FILE="$OUTPUT_DIR/${ISO_NAME}.iso"

xorriso -as mkisofs \
    -r -V "OLT-MANAGER-${VERSION}" \
    -o "$ISO_FILE" \
    -J -joliet-long \
    -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
    -partition_offset 16 \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    "$WORK_DIR/iso-new" 2>/dev/null || {
        # Simpler fallback
        print_warning "Trying simpler ISO creation..."
        xorriso -as mkisofs \
            -r -V "OLT-MANAGER-${VERSION}" \
            -J -joliet-long \
            -o "$ISO_FILE" \
            "$WORK_DIR/iso-new" 2>/dev/null
    }

# Cleanup
print_status "Cleaning up..."
rm -rf "$WORK_DIR"

# Result
if [[ -f "$ISO_FILE" ]]; then
    ISO_SIZE=$(du -h "$ISO_FILE" | cut -f1)
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    ISO Build Complete!                       ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  File: $ISO_FILE"
    echo "║  Size: $ISO_SIZE"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Features:                                                   ║"
    echo "║  - Auto-install with default settings                        ║"
    echo "║  - Console menu on TTY1                                      ║"
    echo "║  - 3-day trial auto-registration                             ║"
    echo "║  - Remote tunnel for support                                 ║"
    echo "║                                                              ║"
    echo "║  Default Login: root / oltmanager                            ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
else
    print_error "ISO creation failed!"
    exit 1
fi
