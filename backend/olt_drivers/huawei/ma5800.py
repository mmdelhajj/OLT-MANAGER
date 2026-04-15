"""Huawei MA5800 driver — chassis-style XGS-PON / GPON OLT (Phase 7.5 stub).

This is the most-requested Huawei model. The MA5800 is a chassis with
swappable line cards; PON port count depends on which cards are
installed. Real implementation will discover cards via
`display board` over SmartAX.
"""

from __future__ import annotations

from ..base import PortLayout
from ._base import HuaweiDriverBase


class MA5800Driver(HuaweiDriverBase):
    MODEL = "MA5800"
    DISPLAY_NAME = "Huawei MA5800 (chassis GPON/XGS-PON)"
    PON_TECH = "GPON"  # Override at runtime once we read the line cards
    PON_COUNT = 0      # Dynamic — set after `display board` parsing
    ALIASES = ["MA5800", "MA5800-X2", "MA5800-X7", "MA5800-X15", "MA5800-X17"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper().replace(" ", "")
        return "MA5800" in m

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        # Placeholder until card discovery is implemented. The number of
        # uplink slots is variable; this is the worst case for an X17.
        return PortLayout(
            sfp_plus_ports=[],
            qsfp_ports=[],
            ge_ports=[],
            sfp_ports=[],
            pon_count=0,
        )
