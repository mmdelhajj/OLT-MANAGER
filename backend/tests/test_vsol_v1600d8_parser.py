"""Driver-level tests for the VSOL V1600D8 driver.

These tests stub out the SNMP and web-scraping helpers so that the driver can
be exercised without a real OLT on the network.
"""

from unittest.mock import patch

import pytest

from olt_drivers.base import DriverPollResult
from olt_drivers.vsol.v1600d8 import V1600D8Driver


def _make_driver():
    return V1600D8Driver("10.0.0.1", "public", "admin", "admin")


def test_v1600d8_metadata():
    assert V1600D8Driver.MODEL == "V1600D8"
    assert V1600D8Driver.PON_TECH == "EPON"
    assert V1600D8Driver.PON_COUNT == 8


def test_v1600d8_matches():
    assert V1600D8Driver.matches("V1600D8")
    assert V1600D8Driver.matches("v1600d8")
    assert V1600D8Driver.matches("VSOL V1600D8")
    assert not V1600D8Driver.matches("V1600D16")
    assert not V1600D8Driver.matches("V1600D-MINI")
    assert not V1600D8Driver.matches("V1600G2-B")
    assert not V1600D8Driver.matches("")
    assert not V1600D8Driver.matches(None)


def test_v1600d8_port_layout():
    layout = _make_driver().get_port_layout()
    assert layout.pon_count == 8
    # SFP=GE1-4
    assert [p[0] for p in layout.sfp_ports] == [1, 2, 3, 4]
    assert all(p[2] == "1G" for p in layout.sfp_ports)
    # SFP+=GE5-8
    assert [p[0] for p in layout.sfp_plus_ports] == [5, 6, 7, 8]
    assert all(p[2] == "10G" for p in layout.sfp_plus_ports)
    # RJ45=GE9-16
    assert [p[0] for p in layout.ge_ports] == list(range(9, 17))


def test_v1600d8_port_mapping_covers_all_uplink_indexes():
    mapping = _make_driver().get_port_layout().to_port_mapping()
    # Index 1-4 SFP, 5-8 SFP+, 9-16 RJ45
    for idx in range(1, 5):
        assert mapping[idx] == ("sfp", idx)
    for idx in range(5, 9):
        assert mapping[idx] == ("xge", idx)
    for idx in range(9, 17):
        assert mapping[idx] == ("ge", idx)


def test_v1600d8_poll_uses_subtree12_snmp_helper():
    """``poll()`` must call ``poll_olt_snmp`` (subtree 12) for V1600D8."""
    fake_onus = [object(), object()]
    fake_status = {"1:1": True, "1:2": False}

    with patch("olt_connector.poll_olt_snmp", return_value=(fake_onus, fake_status)) as mock_snmp, \
         patch("olt_web_scraper.get_onu_opm_data_web", return_value={"AA:BB": {"rx_power": -22.5}}) as mock_opm, \
         patch("olt_connector.get_olt_health_snmp", return_value={"cpu_usage": 12, "uptime_seconds": 9999}) as mock_health, \
         patch("olt_connector.get_traffic_counters_snmp", return_value={1: {"rx_bytes": 100, "tx_bytes": 200}}) as mock_traffic:

        result = _make_driver().poll()

    assert isinstance(result, DriverPollResult)
    mock_snmp.assert_called_once_with("10.0.0.1", "public")
    mock_opm.assert_called_once()
    mock_health.assert_called_once()
    mock_traffic.assert_called_once()

    assert result.onus == fake_onus
    assert result.status_map == fake_status
    assert result.optical_data == {"AA:BB": {"rx_power": -22.5}}
    assert result.health == {"cpu_usage": 12, "uptime_seconds": 9999}
    assert result.port_traffic == {1: {"rx_bytes": 100, "tx_bytes": 200}}
    # V1600D8 returns models inline through the SNMP poll, so the
    # web-scraped models dict is empty.
    assert result.onu_models == {}
    assert result.olt_alive_times == {}


def test_v1600d8_poll_degrades_when_snmp_fails():
    """A failing SNMP poll must not raise — it should return empty results."""
    with patch("olt_connector.poll_olt_snmp", side_effect=RuntimeError("SNMP timeout")), \
         patch("olt_web_scraper.get_onu_opm_data_web", return_value={}), \
         patch("olt_connector.get_olt_health_snmp", return_value={}), \
         patch("olt_connector.get_traffic_counters_snmp", return_value={}):

        result = _make_driver().poll()

    assert result.onus == []
    assert result.status_map == {}


def test_v1600d8_reboot_onu_calls_web_scraper():
    with patch("olt_web_scraper.reboot_onu_web", return_value=True) as mock_reboot:
        ok = _make_driver().reboot_onu(3, 7)
    assert ok is True
    mock_reboot.assert_called_once_with(
        ip="10.0.0.1",
        pon_port=3,
        onu_id=7,
        username="admin",
        password="admin",
        model="V1600D8",
    )


def test_v1600d8_set_onu_description_passes_model():
    with patch("olt_web_scraper.set_onu_description_web", return_value=True) as mock_set:
        ok = _make_driver().set_onu_description(2, 5, "Customer ABC")
    assert ok is True
    kwargs = mock_set.call_args.kwargs
    assert kwargs["model"] == "V1600D8"
    assert kwargs["description"] == "Customer ABC"


def test_v1600d8_delete_onu_calls_web_scraper():
    with patch("olt_web_scraper.delete_onu_web", return_value=True) as mock_delete:
        ok = _make_driver().delete_onu(4, 9, serial="SN-123")
    assert ok is True
    mock_delete.assert_called_once()


def test_v1600d8_get_offline_reason_returns_string():
    with patch(
        "olt_web_scraper.get_onu_offline_reason_web",
        return_value="Power Off",
    ):
        reason = _make_driver().get_offline_reason(1, 2, serial=None)
    assert reason == "Power Off"
