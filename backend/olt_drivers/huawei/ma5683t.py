"""Huawei MA5683T driver — older 2U GPON OLT (Phase 7.5 stub)."""

from __future__ import annotations

from ..base import PortLayout
from ._base import HuaweiDriverBase


class MA5683TDriver(HuaweiDriverBase):
    MODEL = "MA5683T"
    DISPLAY_NAME = "Huawei MA5683T (2U GPON)"
    PON_TECH = "GPON"
    PON_COUNT = 16
    ALIASES = ["MA5683T", "5683T"]

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        return "5683T" in model_string.upper()

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        return PortLayout(pon_count=16)
