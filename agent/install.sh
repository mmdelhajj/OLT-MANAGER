#!/usr/bin/env bash
# OLT Manager Local Agent — Installer
# Usage: curl -sSL https://api.oltmanager.io/agent/install.sh | sudo bash
set -euo pipefail

INSTALL_DIR="/opt/olt-agent"
CONFIG_DIR="/etc/olt-agent"
BACKEND_DIR="$INSTALL_DIR/backend"
SERVICE_NAME="olt-agent"

SAAS_URL="${SAAS_URL:-https://api.oltmanager.io}"

echo "============================================"
echo "  OLT Manager Local Agent Installer"
echo "============================================"
echo ""

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Python 3 not found. Installing..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq && apt-get install -y python3 python3-pip python3-venv
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-pip
    else
        echo "ERROR: Cannot install Python 3. Please install it manually."
        exit 1
    fi
fi

# Install SNMP tools (needed for SNMP polling)
if ! command -v snmpwalk &>/dev/null; then
    echo "Installing SNMP tools..."
    if command -v apt-get &>/dev/null; then
        apt-get install -y snmp snmp-mibs-downloader 2>/dev/null || apt-get install -y snmp
    elif command -v yum &>/dev/null; then
        yum install -y net-snmp-utils
    fi
fi

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BACKEND_DIR"
mkdir -p "$CONFIG_DIR"

# Download agent package
echo "Downloading agent package..."
AGENT_FILES=(
    "agent/agent.py"
    "agent/agent_push.py"
    "agent/payload.py"
    "agent/requirements.txt"
)

for f in "${AGENT_FILES[@]}"; do
    fname=$(basename "$f")
    curl -sSL "$SAAS_URL/$f" -o "$INSTALL_DIR/$fname" 2>/dev/null || true
done

# Download backend modules (the agent reuses these for polling)
BACKEND_FILES=(
    "backend/olt_connector.py"
    "backend/olt_web_scraper.py"
    "backend/mikrotik_traffic.py"
    "backend/config.py"
)

for f in "${BACKEND_FILES[@]}"; do
    fname=$(basename "$f")
    curl -sSL "$SAAS_URL/$f" -o "$BACKEND_DIR/$fname" 2>/dev/null || true
done

# Download driver package
mkdir -p "$BACKEND_DIR/olt_drivers/vsol" "$BACKEND_DIR/olt_drivers/huawei" "$BACKEND_DIR/olt_drivers/zte"
DRIVER_FILES=(
    "backend/olt_drivers/__init__.py"
    "backend/olt_drivers/base.py"
    "backend/olt_drivers/registry.py"
    "backend/olt_drivers/vsol/__init__.py"
    "backend/olt_drivers/vsol/_base.py"
    "backend/olt_drivers/vsol/v1600d4.py"
    "backend/olt_drivers/vsol/v1600d8.py"
    "backend/olt_drivers/vsol/v1600g2b.py"
    "backend/olt_drivers/huawei/__init__.py"
    "backend/olt_drivers/huawei/ma5800.py"
    "backend/olt_drivers/huawei/ma5683t.py"
    "backend/olt_drivers/huawei/ea5800.py"
    "backend/olt_drivers/zte/__init__.py"
    "backend/olt_drivers/zte/c320.py"
    "backend/olt_drivers/zte/c300.py"
    "backend/olt_drivers/zte/c600.py"
)

for f in "${DRIVER_FILES[@]}"; do
    rel="${f#backend/}"
    dir=$(dirname "$BACKEND_DIR/$rel")
    mkdir -p "$dir"
    curl -sSL "$SAAS_URL/$f" -o "$BACKEND_DIR/$rel" 2>/dev/null || true
done

# Create Python virtual environment and install deps
echo "Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv" 2>/dev/null || python3 -m venv "$INSTALL_DIR/venv" --without-pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt" 2>/dev/null || \
    "$INSTALL_DIR/venv/bin/pip" install requests pyyaml pydantic pysnmp routeros_api

# Create config template if not exists
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo ""
    read -rp "Enter your Agent API key (agk_...): " API_KEY
    read -rp "Enter SaaS URL [$SAAS_URL]: " USER_SAAS_URL
    USER_SAAS_URL="${USER_SAAS_URL:-$SAAS_URL}"

    cat > "$CONFIG_DIR/config.yaml" <<YAML
# OLT Manager Local Agent Configuration
saas_url: "$USER_SAAS_URL"
api_key: "$API_KEY"
poll_interval: 30
optical_every: 5

olts:
  - name: "My OLT"
    ip_address: "192.168.1.100"
    model: "V1600D8"
    snmp_community: "public"
    web_username: "admin"
    web_password: "admin"
    mikrotik:
      enabled: false
      ip: "192.168.1.1"
      username: "admin"
      password: ""
      port: 8728
YAML
    chmod 600 "$CONFIG_DIR/config.yaml"
    echo "Config created at $CONFIG_DIR/config.yaml"
else
    echo "Config already exists at $CONFIG_DIR/config.yaml — skipping"
fi

# Create systemd service
cat > "/etc/systemd/system/$SERVICE_NAME.service" <<SERVICE
[Unit]
Description=OLT Manager Local Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=OLT_BACKEND_DIR=$BACKEND_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/agent.py --config $CONFIG_DIR/config.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=olt-agent

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit your OLT config:  nano $CONFIG_DIR/config.yaml"
echo "  2. Start the agent:       systemctl start $SERVICE_NAME"
echo "  3. Check status:          systemctl status $SERVICE_NAME"
echo "  4. View logs:             journalctl -u $SERVICE_NAME -f"
echo ""
echo "The agent will poll your OLTs and push data to the SaaS dashboard."
echo "Credentials (OLT/Mikrotik) stay local — only metrics are sent."
