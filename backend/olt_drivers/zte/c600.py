"""ZTE C600 driver — chassis XGS-PON OLT (Phase 7.5 stub)."""

from __future__ import annotations

from ..base import PortLayout
from ._base import ZTEDriverBase


class C600Driver(ZTEDriverBase):
    MODEL = "C600"
    DISPLAY_NAME = "ZTE C600 (chassis XGS-PON)"
    PON_TECH = "XGS-PON"
    PON_COUNT = 0  # Variable
    ALIASES = ["C600", "ZXA10-C600", "ZXA10 C600", "C650"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper().replace(" ", "")
        return "C600" in m or "C650" in m

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        return PortLayout(pon_count=0)
