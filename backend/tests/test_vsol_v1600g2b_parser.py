"""Driver-level tests for the VSOL V1600G2-B (GPON) driver."""

from unittest.mock import patch

import pytest

from olt_drivers.base import DriverPollResult
from olt_drivers.vsol.v1600g2b import V1600G2BDriver


def _make_driver():
    return V1600G2BDriver("10.0.0.2", "public", "admin", "admin")


def test_v1600g2b_metadata():
    assert V1600G2BDriver.MODEL == "V1600G2-B"
    assert V1600G2BDriver.PON_TECH == "GPON"
    assert V1600G2BDriver.PON_COUNT == 16


def test_v1600g2b_matches():
    assert V1600G2BDriver.matches("V1600G2-B")
    assert V1600G2BDriver.matches("V1600G2")
    assert V1600G2BDriver.matches("v1600g2-b")
    assert V1600G2BDriver.matches("VSOL V1600G2-B")
    assert not V1600G2BDriver.matches("V1600D8")
    assert not V1600G2BDriver.matches("V1600D4")
    assert not V1600G2BDriver.matches("")
    assert not V1600G2BDriver.matches(None)


def test_v1600g2b_port_layout():
    layout = _make_driver().get_port_layout()
    assert layout.pon_count == 16
    # GPON OLT has RJ45(GE1-4), no SFP, SFP+(GE5-8)
    assert [p[0] for p in layout.ge_ports] == [1, 2, 3, 4]
    assert [p[0] for p in layout.sfp_plus_ports] == [5, 6, 7, 8]
    assert layout.sfp_ports == []
    assert layout.qsfp_ports == []


def test_v1600g2b_port_mapping():
    mapping = _make_driver().get_port_layout().to_port_mapping()
    for idx in range(1, 5):
        assert mapping[idx] == ("ge", idx)
    for idx in range(5, 9):
        assert mapping[idx] == ("xge", idx)


def test_v1600g2b_poll_uses_web_scraping_for_onus():
    """V1600G2-B must skip the broken SNMP ONU walk and scrape the web UI."""
    fake_onu_list = [
        {
            "pon_port": 1,
            "onu_id": 1,
            "mac_address": "AA:BB:CC:DD:EE:01",
            "description": "Customer A",
            "model": "HG8546M",
            "is_online": True,
        },
        {
            "pon_port": 2,
            "onu_id": 5,
            "mac_address": "AA:BB:CC:DD:EE:05",
            "description": "Customer B",
            "model": "HG8546M",
            "is_online": False,
        },
    ]
    fake_models = {"1:1": "HG8546M", "2:5": "HG8546M"}
    fake_status_info = {
        "1:1": {"alive_time_seconds": 12345, "deregister_reason": None},
    }
    fake_optical = {"AA:BB:CC:DD:EE:01": {"rx_power": -19.0}}
    fake_health = {"cpu_usage": 18, "uptime_seconds": 5000}
    fake_traffic = {1: {"rx_bytes": 100, "tx_bytes": 200}}

    with patch("olt_web_scraper.get_onu_list_web", return_value=fake_onu_list) as mock_list, \
         patch("olt_web_scraper.get_onu_models_web", return_value=fake_models) as mock_models, \
         patch("olt_web_scraper.get_onu_status_info_web", return_value=fake_status_info) as mock_status, \
         patch("olt_web_scraper.get_onu_opm_data_web", return_value=fake_optical) as mock_opm, \
         patch("olt_connector.get_olt_health_snmp", return_value=fake_health) as mock_health_fn, \
         patch("olt_connector.get_traffic_counters_snmp", return_value=fake_traffic) as mock_traffic_fn:

        result = _make_driver().poll()

    assert isinstance(result, DriverPollResult)
    mock_list.assert_called_once()
    mock_models.assert_called_once()
    mock_status.assert_called_once()
    mock_opm.assert_called_once()
    mock_health_fn.assert_called_once()
    mock_traffic_fn.assert_called_once()

    assert len(result.onus) == 2
    assert result.onus[0].pon_port == 1
    assert result.onus[0].onu_id == 1
    assert result.onus[0].mac_address == "AA:BB:CC:DD:EE:01"
    assert result.onus[0].model == "HG8546M"

    assert result.status_map == {"1:1": True, "2:5": False}
    assert result.onu_models == fake_models
    assert result.olt_alive_times == fake_status_info
    assert result.optical_data == fake_optical
    assert result.health == fake_health
    assert result.port_traffic == fake_traffic


def test_v1600g2b_poll_does_not_call_snmp_onu_helper():
    """The driver must NOT call ``poll_olt_snmp`` (which is broken on G2-B)."""
    with patch("olt_web_scraper.get_onu_list_web", return_value=[]), \
         patch("olt_web_scraper.get_onu_models_web", return_value={}), \
         patch("olt_web_scraper.get_onu_status_info_web", return_value={}), \
         patch("olt_web_scraper.get_onu_opm_data_web", return_value={}), \
         patch("olt_connector.get_olt_health_snmp", return_value={}), \
         patch("olt_connector.get_traffic_counters_snmp", return_value={}), \
         patch("olt_connector.poll_olt_snmp") as mock_snmp_poll:

        _make_driver().poll()

    mock_snmp_poll.assert_not_called()


def test_v1600g2b_poll_handles_web_scraping_failure_gracefully():
    """If the ONU list scrape fails, the driver still returns a valid result."""
    with patch(
        "olt_web_scraper.get_onu_list_web",
        side_effect=RuntimeError("HTTP 500"),
    ), patch("olt_web_scraper.get_onu_models_web", return_value={}), \
         patch("olt_web_scraper.get_onu_status_info_web", return_value={}), \
         patch("olt_web_scraper.get_onu_opm_data_web", return_value={}), \
         patch("olt_connector.get_olt_health_snmp", return_value={}), \
         patch("olt_connector.get_traffic_counters_snmp", return_value={}):

        result = _make_driver().poll()

    assert result.onus == []
    assert result.status_map == {}


def test_v1600g2b_reboot_onu_calls_web_scraper_with_model():
    with patch("olt_web_scraper.reboot_onu_web", return_value=True) as mock_reboot:
        ok = _make_driver().reboot_onu(4, 12)
    assert ok is True
    mock_reboot.assert_called_once_with(
        ip="10.0.0.2",
        pon_port=4,
        onu_id=12,
        username="admin",
        password="admin",
        model="V1600G2-B",
    )
