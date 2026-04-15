"""Driver registry — resolves a model string to the driver class that handles it.

The registry order matters: drivers that match more specific strings (such as
``V1600G2-B``) are checked first so they win against shorter prefix matches.
"""

from __future__ import annotations

from typing import Any, Dict, List, Type

from .base import OLTDriver
from .vsol.v1600g2b import V1600G2BDriver
from .vsol.v1600g1 import V1600G1Driver
from .vsol.v1601g08 import V1601G08Driver
from .vsol.v1601g16 import V1601G16Driver
from .vsol.v1600dmini import V1600DMINIDriver
from .vsol.v1600d16 import V1600D16Driver
from .vsol.v1600d8 import V1600D8Driver
from .vsol.v1600d4 import V1600D4Driver
from .vsol.v1601e04 import V1601E04Driver
from .vsol.v1601e08 import V1601E08Driver

# Phase 7.5 vendor expansion — Huawei + ZTE scaffolds. These match real
# model strings so they show up in the dropdown and the UI can let
# customers add their OLTs, but `poll()` raises NotImplementedError until
# the implementations land.
from .huawei.ma5800 import MA5800Driver
from .huawei.ma5683t import MA5683TDriver
from .huawei.ea5800 import EA5800Driver
from .zte.c320 import C320Driver
from .zte.c300 import C300Driver
from .zte.c600 import C600Driver

# Order: most specific first.
_REGISTRY: List[Type[OLTDriver]] = [
    # VSOL GPON — most specific first
    V1601G16Driver,
    V1601G08Driver,
    V1600G2BDriver,
    V1600G1Driver,
    # VSOL EPON — most specific first
    V1600DMINIDriver,
    V1600D16Driver,
    V1601E08Driver,
    V1601E04Driver,
    V1600D8Driver,
    V1600D4Driver,
    # Huawei
    MA5800Driver,
    MA5683TDriver,
    EA5800Driver,
    # ZTE
    C320Driver,
    C600Driver,
    C300Driver,
]


def get_driver_class(model_string: str) -> Type[OLTDriver]:
    """Return the driver class that handles ``model_string``.

    Raises :class:`ValueError` if no driver matches.
    """
    if not model_string:
        raise ValueError("OLT model is required to resolve a driver")
    for driver_cls in _REGISTRY:
        try:
            if driver_cls.matches(model_string):
                return driver_cls
        except Exception:
            # A buggy ``matches`` must never break resolution of other drivers.
            continue
    raise ValueError(f"No driver found for OLT model: {model_string!r}")


def get_driver(olt: Any) -> OLTDriver:
    """Instantiate a driver for an ``OLT`` database row.

    The ``olt`` argument is duck-typed — it just needs ``model``, ``ip_address``
    and the optional credential fields. Web password is decrypted via
    ``config.decrypt_sensitive`` when present.
    """
    cls = get_driver_class(getattr(olt, "model", None))

    web_username = (
        getattr(olt, "web_username", None)
        or getattr(olt, "username", None)
        or "admin"
    )

    raw_web_password = getattr(olt, "web_password", None) or getattr(
        olt, "password", None
    )
    web_password = "admin"
    if raw_web_password:
        try:
            from config import decrypt_sensitive

            decrypted = decrypt_sensitive(raw_web_password)
            if decrypted:
                web_password = decrypted
        except Exception:
            web_password = raw_web_password or "admin"

    return cls(
        ip=getattr(olt, "ip_address"),
        snmp_community=getattr(olt, "snmp_community", None) or "public",
        web_username=web_username,
        web_password=web_password,
    )


def list_supported_models() -> List[Dict[str, Any]]:
    """Return metadata for every registered driver (used by the dashboard)."""
    return [
        {
            "vendor": d.VENDOR,
            "model": d.MODEL,
            "display_name": d.DISPLAY_NAME,
            "pon_tech": d.PON_TECH,
            "pon_count": d.PON_COUNT,
        }
        for d in _REGISTRY
    ]
