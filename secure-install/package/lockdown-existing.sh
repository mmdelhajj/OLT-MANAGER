#!/bin/bash
#############################################
# OLT Manager - Lockdown Existing Server
# Use this AFTER installing on LUKS system
#############################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "=============================================="
echo "  OLT Manager - System Lockdown"
echo "  Disable all customer access"
echo "=============================================="
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will disable all SSH/console access!${NC}"
echo "Only YOUR SSH key will work after this."
echo ""
read -p "Are you sure? [y/N]: " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    exit 1
fi

echo ""
read -p "Enter YOUR SSH public key: " SUPPORT_SSH_KEY
read -p "Hidden SSH port [2222]: " SUPPORT_PORT
SUPPORT_PORT=${SUPPORT_PORT:-2222}
read -s -p "Support password (backup): " SUPPORT_PASSWORD
echo ""

# Create support user
useradd -m -s /bin/bash -G sudo support_admin 2>/dev/null || true
echo "support_admin:$SUPPORT_PASSWORD" | chpasswd

mkdir -p /home/support_admin/.ssh
echo "$SUPPORT_SSH_KEY" > /home/support_admin/.ssh/authorized_keys
chmod 700 /home/support_admin/.ssh
chmod 600 /home/support_admin/.ssh/authorized_keys
chown -R support_admin:support_admin /home/support_admin/.ssh

# Lock down SSH
cat > /etc/ssh/sshd_config.d/lockdown.conf << EOF
Port $SUPPORT_PORT
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers support_admin
EOF

# Disable root
passwd -l root

# Lock other users
for user in $(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1}'); do
    if [ "$user" != "support_admin" ]; then
        passwd -l "$user" 2>/dev/null || true
        deluser "$user" sudo 2>/dev/null || true
    fi
done

# Disable console
echo "" > /etc/securetty

systemctl restart sshd

echo ""
echo -e "${GREEN}LOCKDOWN COMPLETE!${NC}"
echo ""
echo "Your access: ssh -p $SUPPORT_PORT support_admin@SERVER_IP"
echo ""
echo -e "${RED}All other access is now disabled.${NC}"
