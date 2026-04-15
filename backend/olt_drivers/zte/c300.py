"""ZTE C300 driver — chassis GPON OLT (Phase 7.5 stub)."""

from __future__ import annotations

from ..base import PortLayout
from ._base import ZTEDriverBase


class C300Driver(ZTEDriverBase):
    MODEL = "C300"
    DISPLAY_NAME = "ZTE C300 (chassis GPON)"
    PON_TECH = "GPON"
    PON_COUNT = 0  # Variable — depends on installed line cards
    ALIASES = ["C300", "ZXA10-C300", "ZXA10 C300"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper().replace(" ", "")
        # Don't false-match the C3000 family.
        if "C3000" in m or "C320" in m:
            return False
        return "C300" in m

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        return PortLayout(pon_count=0)
