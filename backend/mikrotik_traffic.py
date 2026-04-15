"""Mikrotik traffic reader — per-ONU rates via PPPoE + FDB mapping.

SNMP ONU counters on EPON OLTs include multicast/broadcast overhead, so
the displayed rates are higher than actual customer traffic.  This module
reads real per-customer traffic from the Mikrotik router instead:

1. Mikrotik PPPoE interface rates  → per-customer download/upload
2. OLT bridge FDB (SNMP)          → maps customer router MAC → ONU ifIndex
3. ONU table in our DB             → maps ifIndex → ONU MAC

The caller gets a dict  ``{onu_mac: {"rx_kbps": ..., "tx_kbps": ...}}``
that can replace SNMP-based rates in the traffic snapshot.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache FDB for 120s — it changes slowly and the walk is expensive
_fdb_cache: Dict[str, Tuple[float, Dict[str, int]]] = {}
_FDB_TTL = 120

# Reuse a small thread pool for parallel SNMP + Mikrotik work
_mk_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="mk")


def _parse_mac_hex(hex_str: str) -> str:
    """'04 5E A4 C7 50 DB' → '04:5E:A4:C7:50:DB'"""
    return ":".join(hex_str.strip().split()).upper()


def _get_olt_fdb(olt_ip: str, community: str = "public") -> Dict[str, int]:
    """Return {router_mac_upper: bridge_port_ifindex} from the OLT FDB.

    Uses dot1dTpFdbAddress + dot1dTpFdbPort (BRIDGE-MIB).
    """
    cache_key = olt_ip
    now = time.time()
    if cache_key in _fdb_cache:
        ts, data = _fdb_cache[cache_key]
        if now - ts < _FDB_TTL:
            return data

    mac_entries: Dict[str, str] = {}  # oid_suffix → MAC
    port_entries: Dict[str, int] = {}  # oid_suffix → port

    try:
        mac_r = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, "-On", olt_ip, "1.3.6.1.2.1.17.4.3.1.1"],
            capture_output=True, text=True, timeout=60,
        )
        for line in mac_r.stdout.strip().split("\n"):
            if "Hex-STRING" in line:
                oid = line.split("=")[0].strip()
                suffix = oid.split("1.3.6.1.2.1.17.4.3.1.1.")[-1]
                mac_hex = line.split("Hex-STRING:")[-1].strip()
                mac_entries[suffix] = _parse_mac_hex(mac_hex)

        port_r = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, "-On", olt_ip, "1.3.6.1.2.1.17.4.3.1.2"],
            capture_output=True, text=True, timeout=60,
        )
        for line in port_r.stdout.strip().split("\n"):
            if "INTEGER" in line:
                oid = line.split("=")[0].strip()
                suffix = oid.split("1.3.6.1.2.1.17.4.3.1.2.")[-1]
                port_entries[suffix] = int(line.split("INTEGER:")[-1].strip())
    except Exception as exc:
        logger.warning("FDB poll failed for %s: %s", olt_ip, exc)
        return _fdb_cache.get(cache_key, (0, {}))[1]

    result: Dict[str, int] = {}
    for suffix, mac in mac_entries.items():
        if suffix in port_entries:
            result[mac] = port_entries[suffix]

    _fdb_cache[cache_key] = (now, result)
    logger.info("OLT FDB for %s: %d MAC→port mappings", olt_ip, len(result))
    return result


def _get_onu_ifindex_map(olt_ip: str, community: str = "public") -> Dict[int, Tuple[int, int]]:
    """Return {ifindex: (pon_port, onu_id)} from ifDescr walk.

    Parses names like 'EPON03ONU5' → (3, 5).
    """
    result: Dict[int, Tuple[int, int]] = {}
    try:
        r = subprocess.run(
            ["snmpwalk", "-v2c", "-c", community, "-On", olt_ip, "1.3.6.1.2.1.2.2.1.2"],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.strip().split("\n"):
            m = re.search(r"\.2\.2\.1\.2\.(\d+)\s*=\s*STRING:\s*\"EPON0?(\d+)ONU(\d+)", line)
            if m:
                idx = int(m.group(1))
                pon = int(m.group(2))
                onu = int(m.group(3))
                result[idx] = (pon, onu)
    except Exception as exc:
        logger.warning("ifDescr walk failed for %s: %s", olt_ip, exc)
    return result


def get_mikrotik_traffic(
    mk_ip: str,
    mk_user: str,
    mk_pass: str,
    mk_port: int,
    olt_ip: str,
    snmp_community: str,
    onu_db_map: Dict[Tuple[int, int], str],
    sample_seconds: int = 3,
) -> Dict[str, Dict[str, float]]:
    """Get per-ONU traffic from Mikrotik PPPoE interfaces.

    Parameters
    ----------
    mk_ip : Mikrotik router IP
    mk_user / mk_pass / mk_port : Mikrotik API credentials
    olt_ip : OLT IP for FDB SNMP query
    snmp_community : SNMP community for OLT
    onu_db_map : {(pon_port, onu_id): onu_mac} from the database
    sample_seconds : how long to sample Mikrotik counters (default 3s)

    Returns
    -------
    {onu_mac: {"rx_kbps": download_kbps, "tx_kbps": upload_kbps}}
    """
    import routeros_api

    # --- Parallel: get FDB + ifIndex map while we talk to Mikrotik ---
    fdb_future = _mk_pool.submit(_get_olt_fdb, olt_ip, snmp_community)
    ifmap_future = _mk_pool.submit(_get_onu_ifindex_map, olt_ip, snmp_community)

    # Connect to Mikrotik and read counters
    try:
        pool = routeros_api.RouterOsApiPool(
            mk_ip, username=mk_user, password=mk_pass,
            port=mk_port, plaintext_login=True,
        )
        api = pool.get_api()
    except Exception as exc:
        logger.error("Mikrotik connection failed %s:%d: %s", mk_ip, mk_port, exc)
        return {}

    try:
        # 1) PPP active sessions: username → caller-id (router MAC)
        active = api.get_resource("/ppp/active").get()
        user_to_mac: Dict[str, str] = {}
        for a in active:
            user_to_mac[a.get("name", "")] = a.get("caller-id", "").upper()

        # 2) PPPoE server interfaces: interface_name → username
        pppoe_srv = api.get_resource("/interface/pppoe-server").get()
        iface_to_user: Dict[str, str] = {}
        for p in pppoe_srv:
            iface_to_user[p.get("name", "")] = p.get("user", "")

        # 3) First counter read (all pppoe-in interfaces)
        ifaces1: Dict[str, Dict[str, int]] = {}
        for iface in api.get_resource("/interface").get():
            if iface.get("type") == "pppoe-in":
                ifaces1[iface.get("name", "")] = {
                    "rx": int(iface.get("rx-byte", "0")),
                    "tx": int(iface.get("tx-byte", "0")),
                }

        time.sleep(sample_seconds)

        # 4) Second counter read
        ifaces2: Dict[str, Dict[str, int]] = {}
        for iface in api.get_resource("/interface").get():
            if iface.get("type") == "pppoe-in":
                ifaces2[iface.get("name", "")] = {
                    "rx": int(iface.get("rx-byte", "0")),
                    "tx": int(iface.get("tx-byte", "0")),
                }
    except Exception as exc:
        logger.error("Mikrotik PPPoE read failed: %s", exc)
        return {}
    finally:
        try:
            pool.disconnect()
        except Exception:
            pass

    # Calculate per-PPPoE rates
    # Mikrotik: tx = to customer = download, rx = from customer = upload
    pppoe_rates: Dict[str, Dict[str, float]] = {}  # router_mac → {down, up}
    for iface_name, c1 in ifaces1.items():
        c2 = ifaces2.get(iface_name)
        if not c2:
            continue
        tx_diff = c2["tx"] - c1["tx"]
        rx_diff = c2["rx"] - c1["rx"]
        if tx_diff < 0 or rx_diff < 0:
            continue  # counter wraparound
        down_kbps = round(tx_diff * 8 / sample_seconds / 1000, 2)
        up_kbps = round(rx_diff * 8 / sample_seconds / 1000, 2)

        # interface name → username → caller-id MAC
        username = iface_to_user.get(iface_name, "")
        router_mac = user_to_mac.get(username, "")
        if router_mac:
            if router_mac not in pppoe_rates:
                pppoe_rates[router_mac] = {"down": 0, "up": 0}
            pppoe_rates[router_mac]["down"] += down_kbps
            pppoe_rates[router_mac]["up"] += up_kbps

    # --- Collect FDB + ifIndex results ---
    fdb = fdb_future.result(timeout=90)   # router_mac → ifindex
    ifmap = ifmap_future.result(timeout=20)  # ifindex → (pon, onu)

    # Build router_mac → onu_mac
    router_to_onu: Dict[str, str] = {}
    for router_mac, port in fdb.items():
        pon_onu = ifmap.get(port)
        if pon_onu:
            onu_mac = onu_db_map.get(pon_onu)
            if onu_mac:
                router_to_onu[router_mac] = onu_mac

    # Map PPPoE rates to ONU MACs
    result: Dict[str, Dict[str, float]] = {}
    for router_mac, rates in pppoe_rates.items():
        onu_mac = router_to_onu.get(router_mac)
        if onu_mac:
            if onu_mac not in result:
                result[onu_mac] = {"rx_kbps": 0, "tx_kbps": 0}
            # rx = download, tx = upload (customer perspective)
            result[onu_mac]["rx_kbps"] += rates["down"]
            result[onu_mac]["tx_kbps"] += rates["up"]

    logger.info(
        "Mikrotik traffic for %s: %d PPPoE sessions, %d with rates → %d ONUs mapped (FDB: %d)",
        mk_ip, len(user_to_mac), len(pppoe_rates), len(result), len(router_to_onu),
    )
    return result
