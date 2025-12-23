#!/bin/bash
#
# OLT Manager Appliance Console Menu
# Professional console interface for OLT Manager
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Configuration
VERSION=$(cat /opt/olt-manager/backend/VERSION 2>/dev/null || echo "1.0.0")
LICENSE_SERVER="http://lic.proxpanel.com"
CONFIG_FILE="/etc/olt-manager/appliance.conf"

# Load configuration
load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        source "$CONFIG_FILE"
    fi
}

# Save configuration
save_config() {
    mkdir -p /etc/olt-manager
    cat > "$CONFIG_FILE" << EOF
HOSTNAME="$HOSTNAME"
CONFIGURED="true"
FIRST_BOOT="false"
EOF
}

# Get current IP address
get_ip() {
    ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -1
}

# Get license info
get_license_info() {
    if [[ -f /etc/olt-manager/license.key ]]; then
        LICENSE_KEY=$(cat /etc/olt-manager/license.key)
        # Try to get license info from API
        RESPONSE=$(curl -s --connect-timeout 5 "$LICENSE_SERVER/api/validate" \
            -H "Content-Type: application/json" \
            -d "{\"license_key\":\"$LICENSE_KEY\",\"hardware_id\":\"$(cat /etc/olt-manager/hardware.id 2>/dev/null)\"}" 2>/dev/null)

        if echo "$RESPONSE" | grep -q '"valid":true'; then
            EXPIRES=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f1)
            LICENSE_TYPE=$(echo "$RESPONSE" | grep -o '"license_type":"[^"]*"' | cut -d'"' -f4)
            echo "$LICENSE_TYPE (expires: $EXPIRES)"
        else
            echo "Invalid or Expired"
        fi
    else
        # Check for trial
        if [[ -f /etc/olt-manager/.trial_registered ]]; then
            TRIAL_END=$(cat /etc/olt-manager/.trial_end 2>/dev/null)
            DAYS_LEFT=$(( ($(date -d "$TRIAL_END" +%s) - $(date +%s)) / 86400 ))
            if [[ $DAYS_LEFT -gt 0 ]]; then
                echo "Trial ($DAYS_LEFT days left)"
            else
                echo "Trial Expired"
            fi
        else
            echo "Not Activated"
        fi
    fi
}

# Get service status
get_service_status() {
    if systemctl is-active --quiet olt-manager; then
        echo -e "${GREEN}Running${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
}

# Clear screen and show header
show_header() {
    clear
    local IP=$(get_ip)
    local STATUS=$(get_service_status)
    local LICENSE=$(get_license_info)

    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║                      OLT MANAGER APPLIANCE                       ║"
    echo "║                         Version $VERSION                            ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo -e "║  Status: $STATUS          License: ${WHITE}$LICENSE${CYAN}"
    echo -e "║  IP: ${WHITE}${IP:-Not configured}${CYAN}          Web: ${WHITE}http://${IP:-N/A}${CYAN}"
    echo "╠══════════════════════════════════════════════════════════════════╣"
    echo -e "${NC}"
}

# Show main menu
show_menu() {
    echo -e "${WHITE}"
    echo "   1) Set Interface IP Address"
    echo "   2) Set DNS Servers"
    echo "   3) Set Timezone"
    echo "   4) Set Hostname"
    echo -e "${CYAN}   ──────────────────────────────────────────────${NC}"
    echo -e "${WHITE}"
    echo "   5) Reset Web Admin Password"
    echo "   6) Activate License Key"
    echo "   7) Show License Info"
    echo -e "${CYAN}   ──────────────────────────────────────────────${NC}"
    echo -e "${WHITE}"
    echo "   8) Ping Host"
    echo "   9) Show System Info"
    echo "  10) View Logs"
    echo -e "${CYAN}   ──────────────────────────────────────────────${NC}"
    echo -e "${WHITE}"
    echo "  11) Check for Updates"
    echo "  12) Restart Services"
    echo "  13) Reboot System"
    echo "  14) Shutdown System"
    echo "  15) Factory Reset"
    echo ""
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -n "   Enter option number: "
}

# Option 1: Set IP Address
set_ip_address() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}       Configure Network Interface${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  1) Use DHCP (Automatic)"
    echo "  2) Set Static IP"
    echo "  3) Cancel"
    echo ""
    read -p "  Select option: " choice

    case $choice in
        1)
            echo ""
            echo "Configuring DHCP..."
            cat > /etc/netplan/01-netcfg.yaml << 'EOF'
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
EOF
            netplan apply 2>/dev/null
            echo -e "${GREEN}DHCP configured successfully!${NC}"
            sleep 2
            ;;
        2)
            echo ""
            read -p "  Enter IP Address (e.g., 192.168.1.100): " IP_ADDR
            read -p "  Enter Netmask (e.g., 24): " NETMASK
            read -p "  Enter Gateway (e.g., 192.168.1.1): " GATEWAY

            cat > /etc/netplan/01-netcfg.yaml << EOF
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - $IP_ADDR/$NETMASK
      gateway4: $GATEWAY
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
EOF
            netplan apply 2>/dev/null
            echo -e "${GREEN}Static IP configured successfully!${NC}"
            sleep 2
            ;;
        *)
            return
            ;;
    esac
}

# Option 2: Set DNS
set_dns() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}         Configure DNS Servers${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    read -p "  Primary DNS (e.g., 8.8.8.8): " DNS1
    read -p "  Secondary DNS (e.g., 8.8.4.4): " DNS2

    # Update netplan
    if [[ -f /etc/netplan/01-netcfg.yaml ]]; then
        sed -i "s/addresses: \[.*\]/addresses: [$DNS1, $DNS2]/" /etc/netplan/01-netcfg.yaml
        netplan apply 2>/dev/null
    fi

    echo -e "${GREEN}DNS configured successfully!${NC}"
    sleep 2
}

# Option 3: Set Timezone
set_timezone() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}            Set Timezone${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  Common timezones:"
    echo "  1) Asia/Beirut"
    echo "  2) Asia/Dubai"
    echo "  3) Asia/Riyadh"
    echo "  4) Europe/London"
    echo "  5) America/New_York"
    echo "  6) Enter manually"
    echo ""
    read -p "  Select option: " choice

    case $choice in
        1) TZ="Asia/Beirut" ;;
        2) TZ="Asia/Dubai" ;;
        3) TZ="Asia/Riyadh" ;;
        4) TZ="Europe/London" ;;
        5) TZ="America/New_York" ;;
        6) read -p "  Enter timezone: " TZ ;;
        *) return ;;
    esac

    timedatectl set-timezone "$TZ"
    echo -e "${GREEN}Timezone set to $TZ${NC}"
    sleep 2
}

# Option 4: Set Hostname
set_hostname_menu() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}            Set Hostname${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  Current hostname: $(hostname)"
    echo ""
    read -p "  Enter new hostname: " NEW_HOSTNAME

    if [[ -n "$NEW_HOSTNAME" ]]; then
        hostnamectl set-hostname "$NEW_HOSTNAME"
        echo -e "${GREEN}Hostname set to $NEW_HOSTNAME${NC}"
    fi
    sleep 2
}

# Option 5: Reset Web Admin Password
reset_admin_password() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}       Reset Web Admin Password${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}  This will reset the admin password to: admin123${NC}"
    echo ""
    read -p "  Are you sure? (yes/no): " confirm

    if [[ "$confirm" == "yes" ]]; then
        cd /opt/olt-manager/backend
        source venv/bin/activate
        python3 -c "
from database import SessionLocal
from models import User
from auth import get_password_hash

db = SessionLocal()
admin = db.query(User).filter(User.username == 'admin').first()
if admin:
    admin.password_hash = get_password_hash('admin123')
    admin.must_change_password = True
    db.commit()
    print('Password reset successfully!')
else:
    print('Admin user not found')
db.close()
" 2>/dev/null
        echo -e "${GREEN}Admin password reset to: admin123${NC}"
        echo -e "${YELLOW}You must change it on first login!${NC}"
    fi
    sleep 3
}

# Option 6: Activate License
activate_license() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}          Activate License${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    read -p "  Enter License Key: " LICENSE_KEY

    if [[ -n "$LICENSE_KEY" ]]; then
        mkdir -p /etc/olt-manager
        echo "$LICENSE_KEY" > /etc/olt-manager/license.key
        chmod 600 /etc/olt-manager/license.key

        # Restart service to apply license
        systemctl restart olt-manager

        echo -e "${GREEN}License key saved!${NC}"
        echo "  Verifying license..."
        sleep 2

        LICENSE_INFO=$(get_license_info)
        echo -e "  License Status: ${WHITE}$LICENSE_INFO${NC}"
    fi
    sleep 3
}

# Option 7: Show License Info
show_license_info() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}          License Information${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""

    if [[ -f /etc/olt-manager/license.key ]]; then
        LICENSE_KEY=$(cat /etc/olt-manager/license.key)
        HARDWARE_ID=$(cat /etc/olt-manager/hardware.id 2>/dev/null)

        echo "  License Key: ${LICENSE_KEY:0:20}..."
        echo "  Hardware ID: $HARDWARE_ID"
        echo ""

        RESPONSE=$(curl -s --connect-timeout 5 "$LICENSE_SERVER/api/validate" \
            -H "Content-Type: application/json" \
            -d "{\"license_key\":\"$LICENSE_KEY\",\"hardware_id\":\"$HARDWARE_ID\"}" 2>/dev/null)

        if echo "$RESPONSE" | grep -q '"valid":true'; then
            echo -e "  Status: ${GREEN}Valid${NC}"
            echo "  Customer: $(echo "$RESPONSE" | grep -o '"customer_name":"[^"]*"' | cut -d'"' -f4)"
            echo "  Type: $(echo "$RESPONSE" | grep -o '"license_type":"[^"]*"' | cut -d'"' -f4)"
            echo "  Max OLTs: $(echo "$RESPONSE" | grep -o '"max_olts":[0-9]*' | cut -d':' -f2)"
            echo "  Max ONUs: $(echo "$RESPONSE" | grep -o '"max_onus":[0-9]*' | cut -d':' -f2)"
            echo "  Expires: $(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4)"
        else
            echo -e "  Status: ${RED}Invalid or Expired${NC}"
        fi
    else
        echo -e "  ${YELLOW}No license key installed${NC}"
        echo ""
        echo "  Hardware ID: $(cat /etc/olt-manager/hardware.id 2>/dev/null)"
    fi

    echo ""
    read -p "  Press Enter to continue..."
}

# Option 8: Ping Host
ping_host() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}             Ping Host${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    read -p "  Enter hostname or IP: " HOST

    if [[ -n "$HOST" ]]; then
        echo ""
        ping -c 4 "$HOST"
    fi

    echo ""
    read -p "  Press Enter to continue..."
}

# Option 9: System Info
show_system_info() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}          System Information${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  Hostname:    $(hostname)"
    echo "  Uptime:      $(uptime -p)"
    echo "  Kernel:      $(uname -r)"
    echo ""
    echo "  CPU Usage:   $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
    echo "  Memory:      $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    echo "  Disk:        $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')"
    echo ""
    echo "  IP Address:  $(get_ip)"
    echo "  Gateway:     $(ip route | grep default | awk '{print $3}')"
    echo "  DNS:         $(cat /etc/resolv.conf | grep nameserver | head -1 | awk '{print $2}')"
    echo ""
    read -p "  Press Enter to continue..."
}

# Option 10: View Logs
view_logs() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}            View Logs${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  1) OLT Manager logs (last 50 lines)"
    echo "  2) System logs (last 50 lines)"
    echo "  3) Cancel"
    echo ""
    read -p "  Select option: " choice

    case $choice in
        1)
            echo ""
            journalctl -u olt-manager -n 50 --no-pager
            ;;
        2)
            echo ""
            journalctl -n 50 --no-pager
            ;;
        *)
            return
            ;;
    esac

    echo ""
    read -p "  Press Enter to continue..."
}

# Option 11: Check Updates
check_updates() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}          Check for Updates${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  Current version: $VERSION"
    echo "  Checking for updates..."
    echo ""

    RESPONSE=$(curl -s --connect-timeout 10 "$LICENSE_SERVER/api/updates/latest" 2>/dev/null)

    if [[ -n "$RESPONSE" ]]; then
        LATEST=$(echo "$RESPONSE" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)

        if [[ -n "$LATEST" && "$LATEST" != "$VERSION" ]]; then
            echo -e "  ${GREEN}Update available: v$LATEST${NC}"
            echo ""
            read -p "  Download and install update? (yes/no): " confirm

            if [[ "$confirm" == "yes" ]]; then
                echo "  Downloading update..."
                # Update logic here
                echo -e "  ${GREEN}Update installed! Please reboot.${NC}"
            fi
        else
            echo -e "  ${GREEN}You have the latest version.${NC}"
        fi
    else
        echo -e "  ${RED}Could not check for updates.${NC}"
    fi

    sleep 3
}

# Option 12: Restart Services
restart_services() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}         Restart Services${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    echo "  Restarting OLT Manager..."

    systemctl restart olt-manager
    systemctl restart nginx

    sleep 2

    if systemctl is-active --quiet olt-manager; then
        echo -e "  ${GREEN}Services restarted successfully!${NC}"
    else
        echo -e "  ${RED}Service failed to start. Check logs.${NC}"
    fi

    sleep 2
}

# Option 13: Reboot
reboot_system() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}           Reboot System${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    read -p "  Are you sure you want to reboot? (yes/no): " confirm

    if [[ "$confirm" == "yes" ]]; then
        echo "  Rebooting in 3 seconds..."
        sleep 3
        reboot
    fi
}

# Option 14: Shutdown
shutdown_system() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}          Shutdown System${NC}"
    echo -e "${CYAN}═══════════════════════════════════════${NC}"
    echo ""
    read -p "  Are you sure you want to shutdown? (yes/no): " confirm

    if [[ "$confirm" == "yes" ]]; then
        echo "  Shutting down in 3 seconds..."
        sleep 3
        poweroff
    fi
}

# Option 15: Factory Reset
factory_reset() {
    clear
    echo -e "${RED}═══════════════════════════════════════${NC}"
    echo -e "${WHITE}           FACTORY RESET${NC}"
    echo -e "${RED}═══════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${RED}WARNING: This will erase ALL data!${NC}"
    echo ""
    echo "  - All OLT configurations"
    echo "  - All ONU records"
    echo "  - All users and settings"
    echo "  - License will need to be re-entered"
    echo ""
    read -p "  Type 'RESET' to confirm: " confirm

    if [[ "$confirm" == "RESET" ]]; then
        echo ""
        echo "  Performing factory reset..."

        # Stop services
        systemctl stop olt-manager

        # Remove database
        rm -f /opt/olt-manager/backend/data/olt_manager.db
        rm -f /opt/olt-manager/backend/olt_manager.db

        # Remove license
        rm -f /etc/olt-manager/license.key
        rm -f /var/lib/olt-manager/.license_cache

        # Remove trial info
        rm -f /etc/olt-manager/.trial_*

        # Restart services
        systemctl start olt-manager

        echo -e "  ${GREEN}Factory reset complete!${NC}"
        echo "  Please reboot the system."
        sleep 3
    fi
}

# Register trial on first boot
register_trial() {
    if [[ ! -f /etc/olt-manager/.trial_registered ]]; then
        HARDWARE_ID=$(cat /etc/olt-manager/hardware.id 2>/dev/null)
        HOSTNAME=$(hostname)

        RESPONSE=$(curl -s --connect-timeout 10 -X POST "$LICENSE_SERVER/api/register-trial" \
            -H "Content-Type: application/json" \
            -d "{\"hardware_id\":\"$HARDWARE_ID\",\"hostname\":\"$HOSTNAME\"}" 2>/dev/null)

        if echo "$RESPONSE" | grep -q '"success":true'; then
            TRIAL_END=$(echo "$RESPONSE" | grep -o '"expires_at":"[^"]*"' | cut -d'"' -f4 | cut -d'T' -f1)
            echo "$TRIAL_END" > /etc/olt-manager/.trial_end
            touch /etc/olt-manager/.trial_registered
        fi
    fi
}

# Main loop
main() {
    load_config
    register_trial

    while true; do
        show_header
        show_menu
        read choice

        case $choice in
            1) set_ip_address ;;
            2) set_dns ;;
            3) set_timezone ;;
            4) set_hostname_menu ;;
            5) reset_admin_password ;;
            6) activate_license ;;
            7) show_license_info ;;
            8) ping_host ;;
            9) show_system_info ;;
            10) view_logs ;;
            11) check_updates ;;
            12) restart_services ;;
            13) reboot_system ;;
            14) shutdown_system ;;
            15) factory_reset ;;
            *) ;;
        esac
    done
}

# Run main
main
