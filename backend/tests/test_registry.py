"""Registry resolution tests."""

import pytest

from olt_drivers.registry import (
    _REGISTRY,
    get_driver_class,
    list_supported_models,
)
from olt_drivers.vsol.v1600d4 import V1600D4Driver
from olt_drivers.vsol.v1600d8 import V1600D8Driver
from olt_drivers.vsol.v1600g2b import V1600G2BDriver


@pytest.mark.parametrize(
    "model_string,expected_cls",
    [
        ("V1600D8", V1600D8Driver),
        ("v1600d8", V1600D8Driver),
        ("VSOL V1600D8", V1600D8Driver),
        ("V1600G2-B", V1600G2BDriver),
        ("V1600G2", V1600G2BDriver),
        ("v1600g2-b", V1600G2BDriver),
        ("V1600D4", V1600D4Driver),
        ("v1600d4", V1600D4Driver),
    ],
)
def test_resolves_correct_driver(model_string, expected_cls):
    assert get_driver_class(model_string) is expected_cls


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        get_driver_class("UNKNOWN-MODEL-XYZ")


def test_empty_model_raises():
    with pytest.raises(ValueError):
        get_driver_class("")
    with pytest.raises(ValueError):
        get_driver_class(None)


def test_d16_not_matched_by_d8():
    """V1600D16 must NOT be matched by the V1600D8 driver."""
    from olt_drivers.vsol.v1600d16 import V1600D16Driver

    assert not V1600D8Driver.matches("V1600D16")
    assert get_driver_class("V1600D16") is V1600D16Driver


def test_d_mini_not_matched_by_d8_or_d4():
    """V1600D-MINI is its own model and must not collide with D4/D8."""
    assert not V1600D8Driver.matches("V1600D-MINI")
    assert not V1600D4Driver.matches("V1600D-MINI")


def test_list_supported_models_includes_vsol_drivers():
    """The original 3 VSOL drivers must always be present.

    Phase 7.5 added Huawei + ZTE scaffolds so the total count grew, but
    the VSOL set is the source-of-truth for the production polling path
    and must not regress.
    """
    models = list_supported_models()
    codes = {m["model"] for m in models}
    assert {"V1600D4", "V1600D8", "V1600G2-B"}.issubset(codes)

    vsol = [m for m in models if m["vendor"] == "VSOL"]
    assert len(vsol) == 10
    for entry in vsol:
        assert entry["pon_count"] > 0
        assert entry["pon_tech"] in ("EPON", "GPON", "XGS-PON", "XG-PON")


def test_phase7_huawei_drivers_registered():
    from olt_drivers.huawei.ma5800 import MA5800Driver
    from olt_drivers.huawei.ma5683t import MA5683TDriver
    from olt_drivers.huawei.ea5800 import EA5800Driver

    assert get_driver_class("MA5800-X7") is MA5800Driver
    assert get_driver_class("Huawei MA5683T") is MA5683TDriver
    assert get_driver_class("EA5800-X15") is EA5800Driver


def test_phase7_zte_drivers_registered():
    from olt_drivers.zte.c320 import C320Driver
    from olt_drivers.zte.c300 import C300Driver
    from olt_drivers.zte.c600 import C600Driver

    assert get_driver_class("ZXA10 C320") is C320Driver
    assert get_driver_class("ZXA10 C300") is C300Driver
    assert get_driver_class("C600") is C600Driver
    # C320 must not be confused with C300:
    assert get_driver_class("C320") is C320Driver
    assert get_driver_class("C300") is C300Driver


def test_registry_order_is_specific_first():
    """Specific GPON drivers come before the more permissive G2-B/G1."""
    g2b_idx = _REGISTRY.index(V1600G2BDriver)
    # V1601G16 and V1601G08 are more specific and come before G2-B
    from olt_drivers.vsol.v1601g16 import V1601G16Driver
    from olt_drivers.vsol.v1601g08 import V1601G08Driver

    assert _REGISTRY.index(V1601G16Driver) < g2b_idx
    assert _REGISTRY.index(V1601G08Driver) < g2b_idx
