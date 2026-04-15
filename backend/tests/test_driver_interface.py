"""Verify that every registered driver implements the abstract interface."""

import inspect

import pytest

from olt_drivers.base import OLTDriver, PortLayout
from olt_drivers.registry import _REGISTRY


@pytest.mark.parametrize("driver_cls", _REGISTRY)
def test_driver_subclass_and_metadata(driver_cls):
    """Every registered driver is an OLTDriver subclass with full metadata.

    PON_COUNT is allowed to be 0 for chassis-style drivers (Huawei MA5800,
    ZTE C300/C600) where the actual port count depends on which line
    cards are installed and is discovered at runtime via `display board`.
    """
    assert issubclass(driver_cls, OLTDriver)
    assert driver_cls.VENDOR, f"{driver_cls.__name__} missing VENDOR"
    assert driver_cls.MODEL, f"{driver_cls.__name__} missing MODEL"
    assert driver_cls.DISPLAY_NAME, f"{driver_cls.__name__} missing DISPLAY_NAME"
    assert driver_cls.PON_TECH in ("EPON", "GPON", "XGS-PON", "XG-PON")
    assert driver_cls.PON_COUNT >= 0


@pytest.mark.parametrize("driver_cls", _REGISTRY)
def test_driver_implements_all_abstract_methods(driver_cls):
    """The class itself must not still be abstract."""
    assert not inspect.isabstract(driver_cls), (
        f"{driver_cls.__name__} still has unimplemented abstract methods: "
        f"{getattr(driver_cls, '__abstractmethods__', set())}"
    )


@pytest.mark.parametrize("driver_cls", _REGISTRY)
def test_driver_can_be_instantiated(driver_cls):
    instance = driver_cls("10.0.0.1", "public", "admin", "admin")
    assert instance.ip == "10.0.0.1"
    assert instance.snmp_community == "public"
    assert instance.web_username == "admin"
    assert instance.web_password == "admin"


@pytest.mark.parametrize("driver_cls", _REGISTRY)
def test_driver_get_port_layout_returns_valid_layout(driver_cls):
    instance = driver_cls("10.0.0.1", "public", "admin", "admin")
    layout = instance.get_port_layout()
    assert isinstance(layout, PortLayout)
    assert layout.pon_count == driver_cls.PON_COUNT

    # Every uplink port spec must be (int_index, str_label, str_speed).
    for spec in (
        layout.sfp_ports
        + layout.sfp_plus_ports
        + layout.ge_ports
        + layout.qsfp_ports
    ):
        assert len(spec) == 3
        if_idx, label, speed = spec
        assert isinstance(if_idx, int) and if_idx > 0
        assert isinstance(label, str) and label
        assert isinstance(speed, str) and speed


@pytest.mark.parametrize("driver_cls", _REGISTRY)
def test_driver_port_mapping_no_duplicates(driver_cls):
    """Two uplink ports of different types must never share an ifIndex."""
    instance = driver_cls("10.0.0.1", "public", "admin", "admin")
    layout = instance.get_port_layout()
    seen_indexes = set()
    for spec in (
        layout.sfp_ports
        + layout.sfp_plus_ports
        + layout.ge_ports
        + layout.qsfp_ports
    ):
        if_idx = spec[0]
        assert if_idx not in seen_indexes, (
            f"{driver_cls.__name__}: ifIndex {if_idx} appears in multiple lists"
        )
        seen_indexes.add(if_idx)
