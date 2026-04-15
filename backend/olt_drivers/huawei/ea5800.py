"""Huawei EA5800 driver — compact pizza-box GPON OLT (Phase 7.5 stub)."""

from __future__ import annotations

from ..base import PortLayout
from ._base import HuaweiDriverBase


class EA5800Driver(HuaweiDriverBase):
    MODEL = "EA5800"
    DISPLAY_NAME = "Huawei EA5800 (compact GPON)"
    PON_TECH = "GPON"
    PON_COUNT = 8
    ALIASES = ["EA5800", "EA5800-X2", "EA5800-X7", "EA5800-X15"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        return "EA5800" in model_string.upper().replace(" ", "")

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        return PortLayout(pon_count=8)
