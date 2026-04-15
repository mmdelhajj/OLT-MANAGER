#!/usr/bin/env python3
"""OLT Manager Local Agent — polls OLTs and pushes data to SaaS.

Runs as a systemd service on the customer's network. Credentials for OLT and
Mikrotik stay local; only polled metrics are sent to the cloud.

Usage:
    python3 agent.py                          # uses /etc/olt-agent/config.yaml
    python3 agent.py --config ./config.yaml   # explicit config path
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml

# The agent reuses backend modules. Make sure they're importable.
BACKEND_DIR = os.environ.get("OLT_BACKEND_DIR", "/opt/olt-agent/backend")
if os.path.isdir(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from payload import AgentPayload, OLTPayload, ONUPayload, PortTrafficPayload
from agent_push import push_payload, send_heartbeat, fetch_config

__version__ = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("olt-agent")


# ---------------------------------------------------------------------------
# State tracking for rate calculation
# ---------------------------------------------------------------------------

@dataclass
class CounterSnapshot:
    rx_bytes: int = 0
    tx_bytes: int = 0
    timestamp: float = 0.0


@dataclass
class AgentState:
    """Per-OLT state kept between poll cycles."""
    # ONU traffic counters: mac_address -> last snapshot
    onu_counters: Dict[str, CounterSnapshot] = field(default_factory=dict)
    # Port traffic counters: if_index -> last snapshot
    port_counters: Dict[int, CounterSnapshot] = field(default_factory=dict)


# Global per-OLT state
_olt_states: Dict[str, AgentState] = {}


def _get_state(olt_ip: str) -> AgentState:
    if olt_ip not in _olt_states:
        _olt_states[olt_ip] = AgentState()
    return _olt_states[olt_ip]


def _calc_rate(prev: CounterSnapshot, cur_rx: int, cur_tx: int, cur_ts: float) -> Tuple[float, float]:
    """Calculate kbps rates from byte counter deltas."""
    if prev.timestamp == 0:
        return 0.0, 0.0
    dt = cur_ts - prev.timestamp
    if dt <= 0:
        return 0.0, 0.0
    rx_diff = cur_rx - prev.rx_bytes
    tx_diff = cur_tx - prev.tx_bytes
    if rx_diff < 0:
        rx_diff = cur_rx
    if tx_diff < 0:
        tx_diff = cur_tx
    rx_kbps = round((rx_diff * 8) / dt / 1000, 2)
    tx_kbps = round((tx_diff * 8) / dt / 1000, 2)
    MAX_KBPS = 10_000_000  # 10 Gbps safety cap
    if rx_kbps > MAX_KBPS or tx_kbps > MAX_KBPS:
        return 0.0, 0.0
    return rx_kbps, tx_kbps


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def poll_one_olt(olt_cfg: dict, skip_optical: bool = False) -> Optional[OLTPayload]:
    """Poll a single OLT and return an OLTPayload."""
    ip = olt_cfg["ip_address"]
    model = olt_cfg.get("model", "")
    snmp_community = olt_cfg.get("snmp_community", "public")
    web_user = olt_cfg.get("web_username", "admin")
    web_pass = olt_cfg.get("web_password", "admin")
    name = olt_cfg.get("name", ip)

    state = _get_state(ip)

    try:
        from olt_drivers import get_driver_class, DriverPollResult

        driver_cls = get_driver_class(model)
        driver = driver_cls(
            ip=ip,
            snmp_community=snmp_community,
            web_username=web_user,
            web_password=web_pass,
        )

        logger.info(f"Polling {name} ({ip}) via {driver_cls.__name__}"
                     + (" (skip optical)" if skip_optical else ""))
        result: DriverPollResult = driver.poll(skip_optical=skip_optical)
    except Exception as e:
        logger.error(f"Poll failed for {name} ({ip}): {e}")
        return OLTPayload(ip_address=ip, name=name, model=model, is_online=False)

    # Build ONU payloads
    onu_payloads: List[ONUPayload] = []
    now_ts = time.time()

    # Get SNMP traffic counters for rate calculation
    snmp_counters: Dict[str, Dict[str, int]] = {}
    try:
        from olt_connector import get_traffic_counters_snmp
        raw_counters = get_traffic_counters_snmp(ip, snmp_community)
        if raw_counters:
            snmp_counters = raw_counters
    except Exception as e:
        logger.warning(f"SNMP traffic counters failed for {name}: {e}")

    # Get Mikrotik traffic if configured
    mk_cfg = olt_cfg.get("mikrotik", {})
    mk_rates: Dict[str, Dict[str, float]] = {}
    if mk_cfg.get("enabled"):
        try:
            from mikrotik_traffic import get_mikrotik_traffic
            # Build onu_db_map from current poll result
            onu_db_map: Dict[Tuple[int, int], str] = {}
            for onu_data in (result.onus or []):
                onu_db_map[(onu_data.pon_port, onu_data.onu_id)] = onu_data.mac_address
            mk_rates = get_mikrotik_traffic(
                mk_ip=mk_cfg["ip"],
                mk_user=mk_cfg.get("username", "admin"),
                mk_pass=mk_cfg.get("password", ""),
                mk_port=mk_cfg.get("port", 8728),
                olt_ip=ip,
                snmp_community=snmp_community,
                onu_db_map=onu_db_map,
            )
            if mk_rates:
                logger.info(f"Mikrotik: {len(mk_rates)} ONUs with traffic from {mk_cfg['ip']}")
        except Exception as e:
            logger.warning(f"Mikrotik traffic failed for {name}: {e}")

    for onu_data in (result.onus or []):
        mac = onu_data.mac_address
        status_key = f"{onu_data.pon_port}:{onu_data.onu_id}"
        is_online = (result.status_map or {}).get(status_key, False)

        # Optical data
        onu_rx_power = None
        onu_tx_power = None
        onu_temperature = None
        onu_voltage = None
        onu_tx_bias = None
        rx_power = onu_data.rx_power

        web_data = (result.optical_data or {}).get(mac) or (result.optical_data or {}).get(status_key)
        if web_data:
            onu_rx_power = web_data.get("onu_rx_power")
            onu_tx_power = web_data.get("tx_power")
            onu_temperature = web_data.get("temperature")
            onu_voltage = web_data.get("voltage")
            onu_tx_bias = web_data.get("tx_bias")
            if rx_power is None and web_data.get("rx_power") is not None:
                rx_power = web_data["rx_power"]

        # Model from web scraping (GPON)
        onu_model = onu_data.model
        if not onu_model and result.onu_models:
            onu_model = result.onu_models.get(status_key)

        # Alive time
        alive_time = None
        if result.olt_alive_times and status_key in result.olt_alive_times:
            alive_time = result.olt_alive_times[status_key].get("alive_time_seconds")

        # Offline reason
        offline_reason = None
        if not is_online and result.olt_alive_times and status_key in result.olt_alive_times:
            offline_reason = result.olt_alive_times[status_key].get("deregister_reason")
            if offline_reason:
                dl = offline_reason.lower()
                if "power" in dl or "dying" in dl:
                    offline_reason = "Power Off"
                elif "los" in dl or "fiber" in dl or "link" in dl:
                    offline_reason = "Fiber Cut"

        # Traffic rates — prefer Mikrotik over SNMP
        rx_kbps = 0.0
        tx_kbps = 0.0
        if mac in mk_rates:
            rx_kbps = mk_rates[mac].get("rx_kbps", 0)
            tx_kbps = mk_rates[mac].get("tx_kbps", 0)
        elif mac in snmp_counters:
            c = snmp_counters[mac]
            prev = state.onu_counters.get(mac, CounterSnapshot())
            rx_kbps, tx_kbps = _calc_rate(prev, c.get("rx_bytes", 0), c.get("tx_bytes", 0), now_ts)
            state.onu_counters[mac] = CounterSnapshot(
                rx_bytes=c.get("rx_bytes", 0),
                tx_bytes=c.get("tx_bytes", 0),
                timestamp=now_ts,
            )

        onu_payloads.append(ONUPayload(
            pon_port=onu_data.pon_port,
            onu_id=onu_data.onu_id,
            mac_address=mac,
            is_online=is_online,
            description=onu_data.description,
            model=onu_model,
            distance=onu_data.distance,
            rx_power=rx_power,
            onu_rx_power=onu_rx_power,
            onu_tx_power=onu_tx_power,
            onu_temperature=onu_temperature,
            onu_voltage=onu_voltage,
            onu_tx_bias=onu_tx_bias,
            rx_kbps=rx_kbps,
            tx_kbps=tx_kbps,
            alive_time_seconds=alive_time,
            offline_reason=offline_reason,
        ))

    # Port traffic
    port_payloads: List[PortTrafficPayload] = []
    try:
        port_mapping = driver.get_port_layout().to_port_mapping()
        for if_idx, counters in (result.port_traffic or {}).items():
            if if_idx in port_mapping:
                port_type, port_num = port_mapping[if_idx]
                prev = state.port_counters.get(if_idx, CounterSnapshot())
                rx_kbps, tx_kbps = _calc_rate(
                    prev,
                    counters.get("rx_bytes", 0),
                    counters.get("tx_bytes", 0),
                    now_ts,
                )
                state.port_counters[if_idx] = CounterSnapshot(
                    rx_bytes=counters.get("rx_bytes", 0),
                    tx_bytes=counters.get("tx_bytes", 0),
                    timestamp=now_ts,
                )
                if rx_kbps > 0 or tx_kbps > 0:
                    port_payloads.append(PortTrafficPayload(
                        if_index=if_idx,
                        port_type=port_type,
                        port_number=port_num,
                        rx_kbps=rx_kbps,
                        tx_kbps=tx_kbps,
                    ))
    except Exception as e:
        logger.warning(f"Port traffic processing failed for {name}: {e}")

    health = dict(result.health or {})
    logger.info(f"Poll complete for {name}: {len(onu_payloads)} ONUs, "
                f"{sum(1 for o in onu_payloads if o.is_online)} online")

    return OLTPayload(
        ip_address=ip,
        name=name,
        model=model,
        is_online=True,
        health=health,
        onus=onu_payloads,
        port_traffic=port_payloads,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="OLT Manager Local Agent")
    parser.add_argument("--config", default="/etc/olt-agent/config.yaml",
                        help="Path to config YAML")
    args = parser.parse_args()

    config = load_config(args.config)
    saas_url = config["saas_url"]
    api_key = config["api_key"]
    # Local config overrides (optional, used as fallback)
    local_olts = config.get("olts", [])

    logger.info(f"OLT Agent v{__version__} starting — SaaS: {saas_url}")

    # Initial heartbeat
    try:
        send_heartbeat(saas_url, api_key)
        logger.info("Heartbeat OK — connected to SaaS")
    except Exception as e:
        logger.warning(f"Initial heartbeat failed: {e}")

    # Fetch config from SaaS (auto-discover OLTs)
    poll_interval = int(config.get("poll_interval", 30))
    optical_every = int(config.get("optical_every", 5))
    olts = local_olts

    try:
        remote_cfg = fetch_config(saas_url, api_key)
        remote_olts = remote_cfg.get("olts", [])
        if remote_olts:
            olts = remote_olts
            poll_interval = int(remote_cfg.get("poll_interval", poll_interval))
            optical_every = int(remote_cfg.get("optical_every", optical_every))
            logger.info(f"Auto-discovered {len(olts)} OLT(s) from SaaS")
        else:
            logger.info("No OLTs from SaaS, using local config")
    except Exception as e:
        logger.warning(f"Could not fetch config from SaaS: {e}")
        if olts:
            logger.info(f"Using {len(olts)} OLT(s) from local config")

    if not olts:
        logger.warning("No OLTs configured — waiting for OLTs to be added in dashboard...")

    logger.info(f"Poll every {poll_interval}s, optical every {optical_every} cycles, "
                f"{len(olts)} OLT(s)")

    cycle_count = 0
    CONFIG_REFRESH_CYCLES = 10  # re-fetch OLT list every N cycles

    while True:
        cycle_start = time.time()

        # Periodically re-fetch OLT list from SaaS to pick up new OLTs
        if cycle_count > 0 and (cycle_count % CONFIG_REFRESH_CYCLES) == 0:
            try:
                remote_cfg = fetch_config(saas_url, api_key)
                remote_olts = remote_cfg.get("olts", [])
                if remote_olts:
                    if len(remote_olts) != len(olts):
                        logger.info(f"OLT list updated: {len(olts)} -> {len(remote_olts)} OLT(s)")
                    olts = remote_olts
                    poll_interval = int(remote_cfg.get("poll_interval", poll_interval))
                    optical_every = int(remote_cfg.get("optical_every", optical_every))
            except Exception as e:
                logger.warning(f"Config refresh failed: {e}")

        if not olts:
            # No OLTs yet — just heartbeat and wait
            try:
                send_heartbeat(saas_url, api_key)
            except Exception:
                pass
            time.sleep(poll_interval)
            cycle_count += 1
            continue

        skip_optical = (cycle_count % optical_every) != 0

        olt_payloads: List[OLTPayload] = []
        for olt_cfg in olts:
            result = poll_one_olt(olt_cfg, skip_optical=skip_optical)
            if result:
                olt_payloads.append(result)

        if olt_payloads:
            payload = AgentPayload(
                timestamp=datetime.utcnow(),
                agent_version=__version__,
                olts=olt_payloads,
            )
            try:
                resp = push_payload(saas_url, api_key, payload.dict())
                onus_processed = resp.get("onus_processed", 0)
                logger.info(f"Push OK — {onus_processed} ONUs processed by SaaS")
            except Exception as e:
                logger.error(f"Push failed: {e}")

        cycle_count += 1
        elapsed = time.time() - cycle_start
        sleep_time = max(0, poll_interval - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()
