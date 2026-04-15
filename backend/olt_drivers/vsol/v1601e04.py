"""VSOL V1601E04 driver — 4 PON EPON OLT.

Front-panel layout:
    SFP(GE1-2)  +  SFP+(GE3-4)  +  RJ45(GE5-8)  +  4 EPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._base import VSOLDriverBase

logger = logging.getLogger(__name__)


class V1601E04Driver(VSOLDriverBase):
    """Driver for the VSOL V1601E04 EPON OLT."""

    MODEL = "V1601E04"
    DISPLAY_NAME = "VSOL V1601E04 (4 PON EPON)"
    PON_TECH = "EPON"
    PON_COUNT = 4
    ALIASES = ["V1601E04", "1601E04"]
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        return "1601E04" in m or "E04" in m

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
