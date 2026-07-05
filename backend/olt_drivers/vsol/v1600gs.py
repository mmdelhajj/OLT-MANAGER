"""VSOL V1600GS driver — 1 PON GPON "mini" OLT.

Covers the single-PON GS family: V1600GS, GS-F, GS-ZF, GS-R, GS-O32
(built-in 1:32 splitter), GS-WB. All are 1-PON GPON and share the VSOL GPON
web-scraping poll path.

Uplink port layout is best-effort (1x RJ45 GE + 1x SFP+); verify against real
hardware if you use the uplink-traffic feature. PON discovery uses PON_COUNT.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._gpon_base import VSOLGPONDriverBase

logger = logging.getLogger(__name__)


class V1600GSDriver(VSOLGPONDriverBase):
    """Driver for the VSOL V1600GS single-PON GPON OLT."""

    MODEL = "V1600GS"
    DISPLAY_NAME = "VSOL V1600GS (1 PON GPON)"
    PON_COUNT = 1
    ALIASES = ["V1600GS", "V1600GS-F", "V1600GS-ZF", "V1600GS-R", "V1600GS-O32", "V1600GS-WB"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        return "V1600GS" in model_string.upper()

    # poll() inherited from VSOLGPONDriverBase

    # ---- Port layout --------------------------------------------------------
    def get_port_layout(self) -> PortLayout:
        return PortLayout(
            ge_ports=[(1, "GE1", "1G")],
            sfp_ports=[],
            sfp_plus_ports=[(2, "GE2", "10G")],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
