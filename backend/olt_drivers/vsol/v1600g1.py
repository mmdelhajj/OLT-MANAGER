"""VSOL V1600G1 driver — 8 PON GPON OLT.

Front-panel layout:
    RJ45(GE1-4)  +  SFP+(GE5-8)  +  8 GPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._gpon_base import VSOLGPONDriverBase

logger = logging.getLogger(__name__)


class V1600G1Driver(VSOLGPONDriverBase):
    """Driver for the VSOL V1600G1 GPON OLT."""

    MODEL = "V1600G1"
    DISPLAY_NAME = "VSOL V1600G1 (8 PON GPON)"
    PON_COUNT = 8
    ALIASES = ["V1600G1", "1600G1"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        # Match V1600G1 but not V1600G2
        if "G2" in m:
            return False
        return "V1600G1" in m or "1600G1" in m

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
