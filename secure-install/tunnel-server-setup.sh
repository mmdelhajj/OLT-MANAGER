#!/bin/bash
#############################################
# License Server - Tunnel Management Setup
# Run this on your license server (109.110.185.70)
#############################################

set -e

echo "=============================================="
echo "  Setting up Tunnel Management Server"
echo "=============================================="

# Create tunnel user
useradd -m -s /bin/bash tunnel_manager 2>/dev/null || true

# Generate SSH key for tunnel connections
mkdir -p /home/tunnel_manager/.ssh
if [ ! -f /home/tunnel_manager/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -f /home/tunnel_manager/.ssh/id_rsa -N "" -C "tunnel-manager"
fi

# Create authorized_keys for incoming tunnels
touch /home/tunnel_manager/.ssh/authorized_keys
chmod 700 /home/tunnel_manager/.ssh
chmod 600 /home/tunnel_manager/.ssh/authorized_keys
chmod 600 /home/tunnel_manager/.ssh/id_rsa
chown -R tunnel_manager:tunnel_manager /home/tunnel_manager/.ssh

# Configure SSH to allow tunnel connections
cat >> /etc/ssh/sshd_config << 'EOF'

# Tunnel connections from customers
Match User tunnel_manager
    AllowTcpForwarding yes
    GatewayPorts yes
    PermitOpen any
    X11Forwarding no
    AllowAgentForwarding no
EOF

# Create tunnel management directory
mkdir -p /opt/tunnel-manager
mkdir -p /opt/tunnel-manager/customers

# Create customer registry
cat > /opt/tunnel-manager/customers.json << 'EOF'
{
    "customers": []
}
EOF

# Create tunnel status script
cat > /opt/tunnel-manager/tunnel-status.sh << 'SCRIPT_EOF'
#!/bin/bash
# Show all active customer tunnels

echo "=============================================="
echo "  Active Customer Tunnels"
echo "=============================================="
echo ""

# Find all tunnel ports
TUNNELS=$(ss -tlnp | grep "127.0.0.1:3" | awk '{print $4}' | cut -d: -f2 | sort -n)

if [ -z "$TUNNELS" ]; then
    echo "No active tunnels"
    exit 0
fi

printf "%-15s %-20s %-10s\n" "PORT" "CUSTOMER" "STATUS"
echo "----------------------------------------------"

for port in $TUNNELS; do
    # Try to get customer info from registry
    CUSTOMER=$(cat /opt/tunnel-manager/customers.json 2>/dev/null | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print(next((c['name'] for c in d['customers'] if c['port']==$port), 'Unknown'))" 2>/dev/null || echo "Unknown")

    # Check if tunnel is responding
    if timeout 2 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        STATUS="ONLINE"
    else
        STATUS="OFFLINE"
    fi

    printf "%-15s %-20s %-10s\n" "$port" "$CUSTOMER" "$STATUS"
done

echo ""
echo "To connect: ssh -p PORT support_admin@127.0.0.1"
SCRIPT_EOF
chmod +x /opt/tunnel-manager/tunnel-status.sh

# Create customer connection script
cat > /opt/tunnel-manager/connect-customer.sh << 'SCRIPT_EOF'
#!/bin/bash
# Connect to a customer server via tunnel

if [ -z "$1" ]; then
    echo "Usage: $0 <port_or_customer_name>"
    echo ""
    /opt/tunnel-manager/tunnel-status.sh
    exit 1
fi

PORT="$1"

# If not a number, look up by name
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    PORT=$(cat /opt/tunnel-manager/customers.json 2>/dev/null | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print(next((c['port'] for c in d['customers'] if '$1'.lower() in c['name'].lower()), ''))" 2>/dev/null)

    if [ -z "$PORT" ]; then
        echo "Customer not found: $1"
        exit 1
    fi
fi

echo "Connecting to customer on port $PORT..."
ssh -p "$PORT" support_admin@127.0.0.1
SCRIPT_EOF
chmod +x /opt/tunnel-manager/connect-customer.sh

# Create add customer script
cat > /opt/tunnel-manager/add-customer.sh << 'SCRIPT_EOF'
#!/bin/bash
# Register a new customer

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <customer_name> <port>"
    echo "Example: $0 'Company ABC' 30001"
    exit 1
fi

NAME="$1"
PORT="$2"

# Add to registry
python3 << PYEOF
import json
with open('/opt/tunnel-manager/customers.json', 'r') as f:
    data = json.load(f)

data['customers'].append({
    'name': '$NAME',
    'port': $PORT,
    'added': '$(date -Iseconds)'
})

with open('/opt/tunnel-manager/customers.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"Added customer: $NAME on port $PORT")
PYEOF
SCRIPT_EOF
chmod +x /opt/tunnel-manager/add-customer.sh

# Add convenient aliases
cat >> /root/.bashrc << 'EOF'

# Tunnel management aliases
alias tunnels='/opt/tunnel-manager/tunnel-status.sh'
alias connect='/opt/tunnel-manager/connect-customer.sh'
alias add-customer='/opt/tunnel-manager/add-customer.sh'
EOF

# Restart SSH
systemctl restart sshd

echo ""
echo "=============================================="
echo "  Tunnel Server Setup Complete!"
echo "=============================================="
echo ""
echo "Commands available:"
echo "  tunnels           - Show all active customer tunnels"
echo "  connect <port>    - Connect to customer server"
echo "  add-customer      - Register new customer"
echo ""
echo "Customer tunnel public key (give this to install script):"
echo "----------------------------------------------"
cat /home/tunnel_manager/.ssh/id_rsa.pub
echo "----------------------------------------------"
echo ""
echo "Save the private key for customer installs:"
echo "  /home/tunnel_manager/.ssh/id_rsa"
