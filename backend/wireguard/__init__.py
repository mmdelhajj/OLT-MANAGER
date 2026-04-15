"""WireGuard hub-and-spoke connectivity for the SaaS (Phase 3).

Each workspace gets a unique virtual /24 carved out of the reserved
10.0.0.0/8 supernet. Customers run a one-line install script that drops
a `wg-quick` config on a Linux/OPNsense gateway and routes their LAN
OLTs into the SaaS via the SaaS-side hub.

See `docs/wireguard-hub.md` for the hub recovery procedure.
"""
