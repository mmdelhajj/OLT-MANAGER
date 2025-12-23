#!/bin/bash
#
# OLT Manager Bootable ISO Builder
# Creates a properly bootable ISO with autoinstall
#

set -e

VERSION=$(cat /root/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
WORK_DIR="/root/olt-iso-work"
OUTPUT_DIR="/root/olt-manager/iso-builder/output"
ISO_NAME="olt-manager-${VERSION}"
UBUNTU_ISO="/root/ubuntu-22.04-server.iso"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*]${NC} $1"; }
print_error() { echo -e "${RED}[X]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       OLT Manager Bootable ISO Builder                       ║"
echo "║                    Version $VERSION                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Cleanup
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"/{source,custom}
mkdir -p "$OUTPUT_DIR"

# Extract original ISO preserving boot info
print_status "Extracting Ubuntu ISO..."
xorriso -osirrox on -indev "$UBUNTU_ISO" -extract / "$WORK_DIR/source" 2>/dev/null

# Copy to custom
cp -a "$WORK_DIR/source/." "$WORK_DIR/custom/"
chmod -R u+w "$WORK_DIR/custom"

# Create autoinstall directory
mkdir -p "$WORK_DIR/custom/autoinstall"

# Create installer package
print_status "Creating installer package..."
PACKAGE_DIR=$(mktemp -d)
mkdir -p "$PACKAGE_DIR/olt-manager"/{backend,scripts}

# Copy backend
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='venv' --exclude='data' --exclude='build' --exclude='dist' \
    /root/olt-manager/backend/ "$PACKAGE_DIR/olt-manager/backend/"

# Copy console script
cp /root/olt-manager/iso-builder/olt-console.sh "$PACKAGE_DIR/olt-manager/scripts/"

# Copy frontend
if [[ -d /var/www/html ]] && [[ -f /var/www/html/index.html ]]; then
    mkdir -p "$PACKAGE_DIR/olt-manager/frontend"
    cp -r /var/www/html/* "$PACKAGE_DIR/olt-manager/frontend/"
fi

# Create tarball
tar -czf "$WORK_DIR/custom/autoinstall/olt-manager.tar.gz" -C "$PACKAGE_DIR" olt-manager
rm -rf "$PACKAGE_DIR"

# Create user-data for autoinstall
print_status "Creating autoinstall configuration..."
cat > "$WORK_DIR/custom/autoinstall/user-data" << 'EOF'
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  identity:
    hostname: olt-manager
    username: root
    password: "$6$xyz$hash"
  ssh:
    install-server: true
    allow-pw: true
  storage:
    layout:
      name: lvm
  late-commands:
    - curtin in-target --target=/target -- bash -c 'echo "root:oltmanager" | chpasswd'
    - mkdir -p /target/opt/olt-manager
    - cp /cdrom/autoinstall/olt-manager.tar.gz /target/opt/
    - curtin in-target --target=/target -- tar -xzf /opt/olt-manager.tar.gz -C /opt/
    - curtin in-target --target=/target -- rm -f /opt/olt-manager.tar.gz
    - cp /cdrom/autoinstall/setup-olt.sh /target/opt/olt-manager/
    - curtin in-target --target=/target -- chmod +x /opt/olt-manager/setup-olt.sh
    - curtin in-target --target=/target -- /opt/olt-manager/setup-olt.sh
EOF

# Create setup script
cat > "$WORK_DIR/custom/autoinstall/setup-olt.sh" << 'SETUP'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
export HOME=/root

# Install packages
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx snmp snmp-mibs-downloader curl wget net-tools openssh-server sshpass

# Setup Python
cd /opt/olt-manager/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q 2>/dev/null || pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt python-multipart aiofiles requests paramiko pysnmp -q

# Console menu
cp /opt/olt-manager/scripts/olt-console.sh /usr/local/bin/olt-console
chmod +x /usr/local/bin/olt-console

# Frontend
if [[ -d /opt/olt-manager/frontend ]]; then
    mkdir -p /var/www/html
    cp -r /opt/olt-manager/frontend/* /var/www/html/
fi

# Systemd service
cat > /etc/systemd/system/olt-manager.service << 'SVC'
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
[Install]
WantedBy=multi-user.target
SVC

# Nginx
cat > /etc/nginx/sites-available/olt-manager << 'NGX'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 50M;
    location / { root /var/www/html; try_files $uri $uri/ /index.html; }
    location /api { proxy_pass http://127.0.0.1:8000; proxy_http_version 1.1; proxy_set_header Host $host; proxy_read_timeout 300; }
    location /ws { proxy_pass http://127.0.0.1:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }
}
NGX
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

# Auto-login console
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'TTY'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
TTY
echo 'if [[ $(tty) == /dev/tty1 ]]; then /usr/local/bin/olt-console; fi' > /root/.bash_profile

# First boot script
cat > /opt/olt-manager/firstboot.sh << 'FB'
#!/bin/bash
mkdir -p /etc/olt-manager
MACHINE_ID=$(cat /etc/machine-id)
MAC=$(ip link show | grep -m1 "link/ether" | awk '{print $2}' | tr -d ':')
HASH=$(echo -n "${MACHINE_ID}${MAC}" | md5sum | cut -d' ' -f1)
HARDWARE_ID="OLT-${HASH:0:8}-${HASH:8:8}-${HASH:16:8}"
echo "$HARDWARE_ID" > /etc/olt-manager/hardware.id
curl -s -X POST "http://lic.proxpanel.com/api/register-trial" -H "Content-Type: application/json" -d "{\"hardware_id\":\"$HARDWARE_ID\"}" >/dev/null 2>&1
RESPONSE=$(curl -s -X POST "http://lic.proxpanel.com/api/tunnel/register" -H "Content-Type: application/json" -d "{\"hardware_id\":\"$HARDWARE_ID\"}" 2>/dev/null)
PORT=$(echo "$RESPONSE" | grep -o '"port":[0-9]*' | cut -d':' -f2)
if [[ -n "$PORT" ]]; then
    echo -e "#!/bin/bash\nexport SSHPASS=\"yo3nFHoe5TXNcEDdTV85\"\nexec sshpass -e ssh -N -R ${PORT}:localhost:22 -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -p 2222 tunnel@lic.proxpanel.com" > /opt/olt-manager/tunnel.sh
    chmod +x /opt/olt-manager/tunnel.sh
    systemctl enable olt-tunnel
    systemctl start olt-tunnel
fi
touch /etc/olt-manager/.firstboot_done
FB
chmod +x /opt/olt-manager/firstboot.sh

cat > /etc/systemd/system/olt-firstboot.service << 'FBS'
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
FBS

cat > /etc/systemd/system/olt-tunnel.service << 'TUN'
[Unit]
Description=OLT Manager Tunnel
After=network-online.target
ConditionPathExists=/opt/olt-manager/tunnel.sh
[Service]
Type=simple
ExecStart=/opt/olt-manager/tunnel.sh
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
TUN

systemctl daemon-reload
systemctl enable olt-manager nginx ssh olt-firstboot
SETUP

# Create meta-data
touch "$WORK_DIR/custom/autoinstall/meta-data"

# Modify GRUB config
print_status "Updating boot configuration..."
cat > "$WORK_DIR/custom/boot/grub/grub.cfg" << 'GRUB'
set timeout=10
set default=0
loadfont unicode

menuentry "Install OLT Manager Appliance" {
    set gfxpayload=keep
    linux /casper/vmlinuz autoinstall ds=nocloud\;s=/cdrom/autoinstall/ quiet ---
    initrd /casper/initrd
}

menuentry "Install OLT Manager (Manual Mode)" {
    set gfxpayload=keep
    linux /casper/vmlinuz quiet ---
    initrd /casper/initrd
}

menuentry "Boot from first hard disk" {
    set root=(hd0)
    chainloader +1
}
GRUB

# Extract MBR and EFI from original ISO
print_status "Extracting boot records from original ISO..."
dd if="$UBUNTU_ISO" bs=1 count=432 of="$WORK_DIR/mbr.bin" 2>/dev/null

# Extract EFI partition
SKIP=$(xorriso -indev "$UBUNTU_ISO" -report_el_torito as_mkisofs 2>&1 | grep -oP '(?<=--interval:appended_partition_2:)\d+')
if [[ -z "$SKIP" ]]; then
    # Alternative: copy efi.img from extracted ISO
    cp "$WORK_DIR/source/boot/grub/efi.img" "$WORK_DIR/efi.img" 2>/dev/null || true
fi

# Create bootable ISO
print_status "Creating bootable ISO..."
ISO_FILE="$OUTPUT_DIR/${ISO_NAME}.iso"

cd "$WORK_DIR/custom"

xorriso -as mkisofs \
    -r -V "OLT-MANAGER" \
    -o "$ISO_FILE" \
    --grub2-mbr "$WORK_DIR/mbr.bin" \
    -partition_offset 16 \
    --mbr-force-bootable \
    -append_partition 2 28732ac11ff8d211ba4b00a0c93ec93b "$WORK_DIR/source/boot/grub/efi.img" \
    -appended_part_as_gpt \
    -iso_mbr_part_type a2a0d0ebe5b9334487c068b6b72699c7 \
    -c '/boot.catalog' \
    -b '/boot/grub/i386-pc/eltorito.img' \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    --grub2-boot-info \
    -eltorito-alt-boot \
    -e '--interval:appended_partition_2:::' \
    -no-emul-boot \
    . 2>&1 || {
        print_status "Trying alternative boot method..."

        # Simpler approach - copy boot structure exactly
        xorriso -as mkisofs \
            -r -V "OLT-MANAGER" \
            -J -joliet-long \
            -b boot/grub/i386-pc/eltorito.img \
            -c boot/grub/boot.cat \
            -no-emul-boot \
            -boot-load-size 4 \
            -boot-info-table \
            -eltorito-alt-boot \
            -e boot/grub/efi.img \
            -no-emul-boot \
            -isohybrid-gpt-basdat \
            -o "$ISO_FILE" \
            . 2>&1
    }

# Cleanup
print_status "Cleaning up..."
rm -rf "$WORK_DIR"

# Verify
if [[ -f "$ISO_FILE" ]]; then
    ISO_SIZE=$(du -h "$ISO_FILE" | cut -f1)
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                  Bootable ISO Created!                       ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  File: $ISO_FILE"
    echo "║  Size: $ISO_SIZE"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  Boot: Select 'Install OLT Manager Appliance'                ║"
    echo "║  Login: root / oltmanager                                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
else
    print_error "ISO creation failed!"
    exit 1
fi
