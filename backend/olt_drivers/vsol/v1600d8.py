"""VSOL V1600D8 driver — 8 PON EPON OLT.

Polling path (parallel via VSOLDriverBase.poll):
    * SNMP via :func:`olt_connector.poll_olt_snmp` (subtree 12 MIB).
    * Optical metrics scraped from the bulk EPON OPM page.
    * Health (CPU/temperature/uptime) via :func:`olt_connector.get_olt_health_snmp`.
    * Uplink port traffic via :func:`olt_connector.get_traffic_counters_snmp`.

Front-panel layout:
    SFP(GE1-4)  +  SFP+(GE5-8)  +  RJ45(GE9-16)  +  8 EPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._base import VSOLDriverBase

logger = logging.getLogger(__name__)


class V1600D8Driver(VSOLDriverBase):
    """Driver for the VSOL V1600D8 EPON OLT."""

    MODEL = "V1600D8"
    DISPLAY_NAME = "VSOL V1600D8 (8 PON EPON)"
    PON_TECH = "EPON"
    PON_COUNT = 8
    ALIASES = ["V1600D8", "1600D8"]
    # V1600D8 reports human-readable port labels via ifName.
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        # ``D8`` must not pick up V1600D16 (the 16-PON sibling) or V1600D-MINI.
        if "D16" in m or "D-MINI" in m:
            return False
        return "D8" in m

    # poll() inherited from VSOLDriverBase (parallel SNMP + optical + health + traffic)

    # ---- Port layout --------------------------------------------------------
    def get_port_layout(self) -> PortLayout:
        return PortLayout(
            sfp_ports=[(i, f"GE{i}", "1G") for i in range(1, 5)],
            sfp_plus_ports=[(i, f"GE{i}", "10G") for i in range(5, 9)],
            ge_ports=[(i, f"GE{i}", "1G") for i in range(9, 17)],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
