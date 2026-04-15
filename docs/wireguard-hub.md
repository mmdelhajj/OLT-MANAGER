# WireGuard Hub Operations Runbook

The SaaS-side WireGuard hub terminates one tunnel per customer workspace.
Every workspace gets a dedicated `/24` carved from the reserved supernet
(default `10.0.0.0/8`, override with `WG_SUPERNET`).

This document covers:

1. Installing the hub from scratch
2. Adding/removing peers manually
3. Recovering from corrupted state
4. Health monitoring
5. Disaster recovery

---

## 1. Hub Bootstrap

### Prerequisites

- A Linux box with a public IPv4 (Hetzner / Fly.io machine / equivalent)
- UDP port `51820` open inbound on the firewall and any cloud security group
- `wireguard-tools` and `iptables` packages
- Root access (the hub runs as root because `wg set` needs `CAP_NET_ADMIN`)

### Install

```bash
apt update && apt install -y wireguard wireguard-tools iptables-persistent

# Generate the hub keypair (KEEP THE PRIVATE KEY SECRET)
umask 077
wg genkey | tee /etc/wireguard/hub.key | wg pubkey > /etc/wireguard/hub.pub

cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address    = 10.0.0.1/8
ListenPort = 51820
PrivateKey = $(cat /etc/wireguard/hub.key)
SaveConfig = true

# Allow the hub to forward packets between workspace subnets and the
# polling worker. The polling worker is on the same machine, so traffic
# from the WG interface to localhost is allowed by default.
PostUp   = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT
EOF

systemctl enable --now wg-quick@wg0
sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
```

### Hand the public key to the SaaS

The customer-facing config blob references the hub's public key. Set:

```
WG_HUB_PUBKEY=<contents of /etc/wireguard/hub.pub>
WG_HUB_ENDPOINT=wg.oltmanager.io:51820
```

These two env vars are what `wireguard.manager.render_client_config()`
splices into every `wg-quick` blob the SaaS hands out.

---

## 2. Adding / Removing Peers Manually

The dashboard usually does this for you via
`POST /api/workspaces/{id}/wireguard/provision`. If you need to do it
out-of-band:

```bash
# ADD peer
wg set wg0 peer <CUSTOMER_PUBKEY> allowed-ips 10.42.7.0/24 persistent-keepalive 25
wg-quick save wg0    # persist to /etc/wireguard/wg0.conf

# REMOVE peer
wg set wg0 peer <CUSTOMER_PUBKEY> remove
wg-quick save wg0
```

---

## 3. Recovery from Corrupted State

If `wg0.conf` is corrupted or out of sync with the database, reconcile from
the database:

```bash
# Stop the broken interface
systemctl stop wg-quick@wg0

# Re-render from the DB
backend/venv/bin/python -m wireguard.cli reconcile-hub
# Reconciles every workspace row's wg_pubkey + wg_subnet against wg0.conf

# Restart
systemctl start wg-quick@wg0
```

The reconciler is **idempotent** — running it twice in a row is safe.

---

## 4. Health Monitoring

A background job calls `wireguard.manager.update_handshakes(db)` every 60
seconds to update each workspace's `wg_status`:

| `wg_status`   | Meaning                                    |
|---------------|--------------------------------------------|
| `pending`     | Peer added to hub but no handshake yet     |
| `connected`   | Last handshake was within 5 minutes        |
| `stale`       | No handshake for >5 minutes (alert worthy) |

Manual health check:

```bash
wg show wg0 latest-handshakes
# Each line: <pubkey> <unix-epoch>
# 0 means "never seen"
```

The dashboard surfaces these as green/yellow/red dots per workspace.

---

## 5. Disaster Recovery

The hub is **stateful** but the state lives in the SaaS database. Losing
the hub host is non-fatal as long as you can rebuild it.

### Procedure

1. Provision a new VM with the same IP (or update DNS for `wg.oltmanager.io`)
2. Run the bootstrap from section 1
3. Restore the same hub keypair from your secrets backup (Vault/1Password)
4. Run `python -m wireguard.cli reconcile-hub` to re-add every peer
5. Customers will reconnect automatically thanks to `PersistentKeepalive`

If you cannot recover the hub keypair you must rotate it:

1. Generate a new keypair
2. Update `WG_HUB_PUBKEY` env var in the SaaS app
3. Force-regenerate every workspace config (`POST /provision` again)
4. **Email every customer** with the new install instructions (their old
   client config is now invalid)

This is **highly disruptive** — protect the hub keypair like a CA root key.

---

## 6. Limits

| Resource | Limit | Note |
|---|---|---|
| Concurrent peers per hub | ~10,000 | Linux kernel WG handles this fine |
| Subnets in /8 supernet | 65,536 | 1 /24 per workspace = ~65k workspaces |
| Bandwidth | NIC-bound | Polling traffic is small (KB/s per OLT) |

When you outgrow one hub, shard by region: each Fly.io region runs its own
hub, and `WG_HUB_ENDPOINT` is set per-region in the worker.
