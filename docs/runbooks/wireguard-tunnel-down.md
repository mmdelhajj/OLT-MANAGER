# Runbook: WireGuard tunnel down

## Symptom
- Workspace status is `pending` or `stale` in the dashboard
- Polling worker logs `connection refused` / `no route to host` for OLTs in
  that workspace
- Grafana alert: "WG peer count dropped > 10% in 5 min"

## Diagnosis

1. SSH to the WG hub and check the peer:
   ```bash
   wg show wg0 | grep -A4 <workspace-pubkey>
   ```
2. `latest handshake` < 3 minutes ago = healthy. > 5 minutes = stale.
3. Check the customer-side gateway is reachable:
   ```bash
   ping -c3 10.<tid>.<wid>.2     # client tunnel address
   ```
4. Check the customer's NAT gateway is up — ask them, or ping their
   public IP if they shared it.

## Fix

- **Stale peer (no handshake)** — usually customer-side. Have them run:
  ```bash
  sudo systemctl restart wg-quick@oltmanager
  sudo wg show
  ```
- **Hub-side peer missing entirely** — re-run reconciliation:
  ```bash
  flyctl ssh console -a olt-manager
  python -m wireguard.cli reconcile-hub
  ```
- **Hub down** — `systemctl restart wg-quick@wg0` on the hub. Check
  `journalctl -u wg-quick@wg0 -n 50`.
- **Subnet collision** — extremely rare. Check the allocator picked a
  unique /24 and that no other peer claims overlapping `AllowedIPs`:
  ```bash
  python -m wireguard.cli list-peers
  ```

## Verify
- `python -m wireguard.cli poll-handshakes` shows the workspace as `connected`
- Workspace dashboard turns green within 60s
- Polling worker successfully reaches the customer's OLT

## Postmortem
- If multiple workspaces went stale at once, suspect the hub box itself
  (kernel module crash, network partition, full disk on `/etc/wireguard/`)
- Capture `wg show` and `journalctl -u wg-quick@wg0` before restarting
