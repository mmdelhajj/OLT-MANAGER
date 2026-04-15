"""VSOL V1601E08 driver — 8 PON EPON OLT.

Front-panel layout:
    SFP(GE1-4)  +  SFP+(GE5-8)  +  RJ45(GE9-16)  +  8 EPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._base import VSOLDriverBase

logger = logging.getLogger(__name__)


class V1601E08Driver(VSOLDriverBase):
    """Driver for the VSOL V1601E08 EPON OLT."""

    MODEL = "V1601E08"
    DISPLAY_NAME = "VSOL V1601E08 (8 PON EPON)"
    PON_TECH = "EPON"
    PON_COUNT = 8
    ALIASES = ["V1601E08", "1601E08"]
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        # Must not match V1601E04
        if "E04" in m:
            return False
        return "1601E08" in m or "E08" in m

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
