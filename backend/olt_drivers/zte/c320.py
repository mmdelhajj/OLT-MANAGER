"""ZTE C320 driver — 1U compact GPON OLT (Phase 7.5 stub)."""

from __future__ import annotations

from ..base import PortLayout
from ._base import ZTEDriverBase


class C320Driver(ZTEDriverBase):
    MODEL = "C320"
    DISPLAY_NAME = "ZTE C320 (1U GPON)"
    PON_TECH = "GPON"
    PON_COUNT = 8
    ALIASES = ["C320", "ZXA10-C320", "ZXA10 C320"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper().replace(" ", "")
        return "C320" in m and "C3200" not in m

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        return PortLayout(pon_count=8)
