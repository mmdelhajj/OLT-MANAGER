"""VSOL V1600D4 driver — 4 PON EPON OLT.

Polling path (parallel via VSOLDriverBase.poll):
    SNMP via subtree 12, optical via the bulk EPON OPM page, plus the standard
    health and traffic helpers. Only the PON count and front-panel layout differ.

Front-panel layout:
    SFP(GE1-2)  +  SFP+(GE3-4)  +  RJ45(GE5-8)  +  4 EPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._base import VSOLDriverBase

logger = logging.getLogger(__name__)


class V1600D4Driver(VSOLDriverBase):
    """Driver for the VSOL V1600D4 EPON OLT."""

    MODEL = "V1600D4"
    DISPLAY_NAME = "VSOL V1600D4 (4 PON EPON)"
    PON_TECH = "EPON"
    PON_COUNT = 4
    ALIASES = ["V1600D4", "1600D4"]
    # The V1600D line reports human-readable port labels via ifName.
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        # ``D4`` must not catch the long-uplink V1600D4-L variant or D-MINI.
        if "D-MINI" in m or "D4-L" in m:
            return False
        return "D4" in m

    # poll() inherited from VSOLDriverBase (parallel SNMP + optical + health + traffic)

    # ---- Port layout --------------------------------------------------------
    def get_port_layout(self) -> PortLayout:
        return PortLayout(
            sfp_ports=[(1, "GE1", "1G"), (2, "GE2", "1G")],
            sfp_plus_ports=[(3, "GE3", "10G"), (4, "GE4", "10G")],
            ge_ports=[(i, f"GE{i}", "1G") for i in range(5, 9)],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
