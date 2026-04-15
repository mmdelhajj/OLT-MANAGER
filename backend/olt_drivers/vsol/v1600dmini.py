"""VSOL V1600D-MINI driver — 2 PON EPON OLT.

Front-panel layout:
    SFP(GE1)  +  SFP+(GE2)  +  RJ45(GE3-4)  +  2 EPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._base import VSOLDriverBase

logger = logging.getLogger(__name__)


class V1600DMINIDriver(VSOLDriverBase):
    """Driver for the VSOL V1600D-MINI EPON OLT."""

    MODEL = "V1600D-MINI"
    DISPLAY_NAME = "VSOL V1600D-MINI (2 PON EPON)"
    PON_TECH = "EPON"
    PON_COUNT = 2
    ALIASES = ["V1600D-MINI", "V1600DMINI", "1600D-MINI"]
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        return "D-MINI" in model_string.upper() or "DMINI" in model_string.upper()

    # poll() inherited from VSOLDriverBase (parallel SNMP + optical + health + traffic)

    # ---- Port layout --------------------------------------------------------
    def get_port_layout(self) -> PortLayout:
        return PortLayout(
            sfp_ports=[(1, "GE1", "1G")],
            sfp_plus_ports=[(2, "GE2", "10G")],
            ge_ports=[(3, "GE3", "1G"), (4, "GE4", "1G")],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
