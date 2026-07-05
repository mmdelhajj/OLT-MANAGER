"""VSOL V1600GT driver — 2 PON GPON OLT.

Covers the low-density GT family: V1600GT, V1600GT-2F. Both are 2-PON GPON and
share the VSOL GPON web-scraping poll path.

Uplink port layout is best-effort (2x RJ45 GE + 2x SFP+); verify against real
hardware if you use the uplink-traffic feature. PON discovery uses PON_COUNT.
"""

from __future__ import annotations

import logging

from ..base import PortLayout
from ._gpon_base import VSOLGPONDriverBase

logger = logging.getLogger(__name__)


class V1600GTDriver(VSOLGPONDriverBase):
    """Driver for the VSOL V1600GT 2-PON GPON OLT."""

    MODEL = "V1600GT"
    DISPLAY_NAME = "VSOL V1600GT (2 PON GPON)"
    PON_COUNT = 2
    ALIASES = ["V1600GT", "V1600GT-2F"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        return "V1600GT" in model_string.upper()

    # poll() inherited from VSOLGPONDriverBase

    # ---- Port layout --------------------------------------------------------
    def get_port_layout(self) -> PortLayout:
        return PortLayout(
            ge_ports=[(i, f"GE{i}", "1G") for i in range(1, 3)],
            sfp_ports=[],
            sfp_plus_ports=[(i, f"GE{i}", "10G") for i in range(3, 5)],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
