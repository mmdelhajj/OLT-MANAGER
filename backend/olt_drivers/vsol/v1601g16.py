"""VSOL V1601G16 driver — 16 PON GPON OLT.

Front-panel layout:
    RJ45(GE1-4)  +  SFP+(GE5-8)  +  16 GPON ports.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._gpon_base import VSOLGPONDriverBase

logger = logging.getLogger(__name__)


class V1601G16Driver(VSOLGPONDriverBase):
    """Driver for the VSOL V1601G16 GPON OLT."""

    MODEL = "V1601G16"
    DISPLAY_NAME = "VSOL V1601G16 (16 PON GPON)"
    PON_COUNT = 16
    ALIASES = ["V1601G16", "1601G16"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        return "1601G16" in m or "G16" in m

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
