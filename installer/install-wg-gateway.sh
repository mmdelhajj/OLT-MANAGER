#!/usr/bin/env bash
# OLT Manager WireGuard Gateway installer (Phase 3.4)
#
# Run this on the customer's on-prem Linux box (or OPNsense host) to:
#   1. Install wireguard-tools
#   2. Pull the workspace's wg-quick config from the SaaS
#   3. Drop it into /etc/wireguard/oltmanager.conf
#   4. Enable the wg-quick@oltmanager systemd unit
#   5. Configure IP forwarding + iptables NAT for OLTs on the LAN
#   6. POST a connected heartbeat back to the SaaS
#
# Usage:
#     curl -sSL https://oltmanager.io/install.sh | sudo bash -s -- \
#         --token <workspace-token> \
#         --olt 192.168.1.10
#
# Or interactive (the script prompts for the token if not given).
set -euo pipefail

API_BASE="${OLT_API_BASE:-https://app.oltmanager.io}"
WG_CONFIG_PATH="/etc/wireguard/oltmanager.conf"
WG_UNIT="wg-quick@oltmanager"
TOKEN=""
LAN_OLT_IPS=()

usage() {
    cat <<EOF
OLT Manager WireGuard Gateway installer

Options:
  --token <jwt>     Workspace token from the dashboard (required)
  --olt <ip>        LAN IP of an OLT to route into the tunnel (repeatable)
  --api  <url>      Override API base URL (default: $API_BASE)
  -h, --help        Show this message

The token can also be provided via the OLT_WORKSPACE_TOKEN env var.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --token) TOKEN="$2"; shift 2 ;;
        --olt)   LAN_OLT_IPS+=("$2"); shift 2 ;;
        --api)   API_BASE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

if [[ -z "$TOKEN" ]]; then
    TOKEN="${OLT_WORKSPACE_TOKEN:-}"
fi

if [[ -z "$TOKEN" ]]; then
    read -rsp "Paste your workspace token: " TOKEN
    echo
fi

if [[ -z "$TOKEN" ]]; then
    echo "ERROR: workspace token is required" >&2
    exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: must be run as root (sudo)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. Install wireguard-tools
# ---------------------------------------------------------------------------

detect_pkg_manager() {
    if   command -v apt-get >/dev/null 2>&1; then echo apt
    elif command -v dnf     >/dev/null 2>&1; then echo dnf
    elif command -v yum     >/dev/null 2>&1; then echo yum
    elif command -v apk     >/dev/null 2>&1; then echo apk
    elif command -v opkg    >/dev/null 2>&1; then echo opkg
    elif command -v pkg     >/dev/null 2>&1; then echo pkg
    else echo unknown
    fi
}

install_wireguard() {
    if command -v wg >/dev/null 2>&1; then
        echo "[install] wireguard-tools already present"
        return
    fi
    local pm
    pm=$(detect_pkg_manager)
    case "$pm" in
        apt)  apt-get update && apt-get install -y wireguard wireguard-tools iptables curl ;;
        dnf)  dnf install -y wireguard-tools iptables curl ;;
        yum)  yum install -y wireguard-tools iptables curl ;;
        apk)  apk add --no-cache wireguard-tools iptables curl ;;
        opkg) opkg update && opkg install wireguard-tools iptables curl ;;
        pkg)  pkg install -y wireguard ;;
        *)    echo "ERROR: unsupported distro — install wireguard-tools manually"; exit 1 ;;
    esac
}

install_wireguard

# ---------------------------------------------------------------------------
# 2. Pull config from SaaS
# ---------------------------------------------------------------------------

# The token encodes workspace_id (and hits an authenticated route).
WORKSPACE_ID=$(echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | grep -oE '"workspace_id":"[^"]+"' | cut -d'"' -f4 || true)
if [[ -z "$WORKSPACE_ID" ]]; then
    echo "ERROR: token does not contain a workspace_id claim" >&2
    exit 1
fi

echo "[install] Fetching WireGuard config for workspace $WORKSPACE_ID"

CFG_URL="$API_BASE/api/workspaces/$WORKSPACE_ID/wireguard/config"
HTTP_CODE=$(curl -s -o /tmp/wg-config.json -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" "$CFG_URL")

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "ERROR: config fetch failed (HTTP $HTTP_CODE)" >&2
    cat /tmp/wg-config.json >&2 || true
    exit 1
fi

# Parse the wg-quick blob out of the JSON. We avoid jq so the install
# script has zero non-stock dependencies.
python3 - <<'PY' > "$WG_CONFIG_PATH"
import json
with open("/tmp/wg-config.json") as f:
    data = json.load(f)
print(data["config"])
PY

chmod 600 "$WG_CONFIG_PATH"
echo "[install] Wrote $WG_CONFIG_PATH"

# Pull the assigned CIDR for downstream NAT setup.
WG_CIDR=$(python3 - <<'PY'
import json
with open("/tmp/wg-config.json") as f:
    print(json.load(f)["cidr"])
PY
)

# ---------------------------------------------------------------------------
# 3. IP forwarding + DNAT rules for each LAN-side OLT
# ---------------------------------------------------------------------------

echo "[install] Enabling IPv4 forwarding"
sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q "^net.ipv4.ip_forward" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Each customer OLT gets a dedicated /32 inside the workspace's /24.
# We start at .10 and bump per OLT so the SaaS sees stable virtual IPs.
i=10
for olt in "${LAN_OLT_IPS[@]}"; do
    base_cidr="${WG_CIDR%/*}"
    octets="${base_cidr%.*}"
    virtual="$octets.$i"
    echo "[install] Mapping virtual $virtual -> LAN $olt"
    iptables -t nat -A PREROUTING -d "$virtual" -j DNAT --to-destination "$olt"
    iptables -t nat -A POSTROUTING -d "$olt" -j MASQUERADE
    i=$((i + 1))
done

# Persist iptables rules so they survive reboot. Distro-dependent.
if command -v iptables-save >/dev/null 2>&1; then
    if [[ -d /etc/iptables ]]; then
        iptables-save > /etc/iptables/rules.v4
    elif [[ -f /etc/sysconfig/iptables ]]; then
        iptables-save > /etc/sysconfig/iptables
    fi
fi

# ---------------------------------------------------------------------------
# 4. Bring up the tunnel
# ---------------------------------------------------------------------------

echo "[install] Starting $WG_UNIT"
systemctl enable "$WG_UNIT" >/dev/null 2>&1 || true
systemctl restart "$WG_UNIT"

sleep 2
if ! wg show oltmanager >/dev/null 2>&1; then
    echo "ERROR: WireGuard interface failed to come up" >&2
    journalctl -u "$WG_UNIT" --no-pager -n 50 || true
    exit 1
fi

# ---------------------------------------------------------------------------
# 5. Heartbeat to the SaaS
# ---------------------------------------------------------------------------

curl -sf -X POST \
    -H "Authorization: Bearer $TOKEN" \
    "$API_BASE/api/workspaces/$WORKSPACE_ID/wireguard/heartbeat" \
    >/dev/null \
    && echo "[install] Heartbeat acknowledged" \
    || echo "[install] WARNING: heartbeat failed (tunnel may still be up)"

cat <<EOF

==============================================================
  WireGuard gateway installed for workspace $WORKSPACE_ID
==============================================================

  Subnet:    $WG_CIDR
  Config:    $WG_CONFIG_PATH
  Service:   $WG_UNIT
  Status:    $(wg show oltmanager latest-handshakes 2>/dev/null | head -n 1 || echo unknown)

  Next steps:
    1. Add your OLT(s) in the dashboard using the *virtual* IP shown above.
    2. The SaaS polling worker will start collecting data within 60s.
    3. Tail logs with:  journalctl -u $WG_UNIT -f
EOF
