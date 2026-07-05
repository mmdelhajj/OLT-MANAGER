"""Tests for the added VSOL GPON pizza-box drivers: V1600GS/GT/G0."""

from olt_drivers import get_driver_class, check_model_support
from olt_drivers.vsol.v1600gs import V1600GSDriver
from olt_drivers.vsol.v1600gt import V1600GTDriver
from olt_drivers.vsol.v1600g0 import V1600G0Driver


def test_metadata_and_pon_counts():
    assert (V1600GSDriver.MODEL, V1600GSDriver.PON_COUNT, V1600GSDriver.PON_TECH) == ("V1600GS", 1, "GPON")
    assert (V1600GTDriver.MODEL, V1600GTDriver.PON_COUNT, V1600GTDriver.PON_TECH) == ("V1600GT", 2, "GPON")
    assert (V1600G0Driver.MODEL, V1600G0Driver.PON_COUNT, V1600G0Driver.PON_TECH) == ("V1600G0", 4, "GPON")


def test_registry_routing_and_variants():
    # Canonical + common variants resolve to the right driver
    for s in ("V1600GS", "V1600GS-F", "V1600GS-O32", "vsol v1600gs-r"):
        assert get_driver_class(s) is V1600GSDriver, s
    for s in ("V1600GT", "V1600GT-2F"):
        assert get_driver_class(s) is V1600GTDriver, s
    for s in ("V1600G0", "V1600G0-B", "V1600G0-R"):
        assert get_driver_class(s) is V1600G0Driver, s


def test_no_collision_with_g1_g2():
    # The new drivers must not steal G1/G2/G08/G16, and vice-versa.
    from olt_drivers.vsol.v1600g1 import V1600G1Driver
    from olt_drivers.vsol.v1600g2b import V1600G2BDriver

    assert get_driver_class("V1600G1") is V1600G1Driver
    assert get_driver_class("V1600G2-B") is V1600G2BDriver
    assert not V1600GSDriver.matches("V1600G2-B")
    assert not V1600G0Driver.matches("V1600G1")
    assert not V1600GTDriver.matches("V1600G2")


def test_now_supported_not_unknown():
    for s in ("V1600GS", "V1600GT", "V1600G0"):
        assert check_model_support(s)["status"] == "supported", s


def test_port_layout_pon_count():
    assert V1600GSDriver("1.1.1.1").get_port_layout().pon_count == 1
    assert V1600GTDriver("1.1.1.1").get_port_layout().pon_count == 2
    assert V1600G0Driver("1.1.1.1").get_port_layout().pon_count == 4
