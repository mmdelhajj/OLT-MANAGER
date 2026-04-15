"""VSOL V1600G2-B driver — 16 PON GPON OLT.

Front-panel layout:
    RJ45(GE1-4)  +  SFP+(GE5-8)  +  16 GPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._gpon_base import VSOLGPONDriverBase

logger = logging.getLogger(__name__)


class V1600G2BDriver(VSOLGPONDriverBase):
    """Driver for the VSOL V1600G2-B GPON OLT."""

    MODEL = "V1600G2-B"
    DISPLAY_NAME = "VSOL V1600G2-B (16 PON GPON)"
    PON_COUNT = 16
    ALIASES = ["V1600G2-B", "V1600G2", "V1600G"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        # Must not match V1600G1 or V1601G08/G16
        if "V1600G1" in m and "G2" not in m:
            return False
        if "V1601G" in m:
            return False
        return "G2" in m or "V1600G" in m

    # poll() inherited from VSOLGPONDriverBase

    # ---- Port layout --------------------------------------------------------
    def get_port_layout(self) -> PortLayout:
        return PortLayout(
            ge_ports=[(i, f"GE{i}", "1G") for i in range(1, 5)],
            sfp_ports=[],
            sfp_plus_ports=[(i, f"GE{i}", "10G") for i in range(5, 9)],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
