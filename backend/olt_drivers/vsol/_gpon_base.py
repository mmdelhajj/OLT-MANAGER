"""Shared polling logic for VSOL GPON OLT models.

All VSOL GPON OLTs use the same web-scraping approach for ONU discovery
(``onuauthinfo.html``), model lookup, status info, and optical metrics.
They differ only in PON count and port layout.

EPON models use the SNMP-based ``poll()`` in ``_base.VSOLDriverBase`` instead.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..base import DriverPollResult
from ._base import VSOLDriverBase, _poll_pool

logger = logging.getLogger(__name__)


class VSOLGPONDriverBase(VSOLDriverBase):
    """Base for VSOL GPON OLTs — polls via web scraping instead of SNMP."""

    PON_TECH = "GPON"

    # ---- helpers for parallel submission ------------------------------------
    def _poll_onu_list(self):
        from olt_connector import ONUData
        from olt_web_scraper import get_onu_list_web

        onus = []
        status_map: Dict[str, bool] = {}
        web_onu_list = get_onu_list_web(self.ip, self.web_username, self.web_password) or []
        for onu in web_onu_list:
            onus.append(ONUData(
                pon_port=onu["pon_port"],
                onu_id=onu["onu_id"],
                mac_address=onu["mac_address"],
                description=onu.get("description"),
                model=onu.get("model"),
            ))
            status_map[f"{onu['pon_port']}:{onu['onu_id']}"] = onu.get("is_online", True)
        return onus, status_map

    def _poll_onu_models(self):
        from olt_web_scraper import get_onu_models_web
        return get_onu_models_web(self.ip, self.web_username, self.web_password) or {}

    def _poll_status_info(self):
        from olt_web_scraper import get_onu_status_info_web
        return get_onu_status_info_web(self.ip, self.web_username, self.web_password) or {}

    # ---- Polling (parallel) -------------------------------------------------
    def poll(self, skip_optical: bool = False) -> DriverPollResult:
        from olt_connector import get_traffic_counters_snmp

        futures: dict[str, Any] = {}

        # Submit all tasks in parallel
        futures["onu_list"] = _poll_pool.submit(self._poll_onu_list)
        futures["models"] = _poll_pool.submit(self._poll_onu_models)
        futures["health"] = _poll_pool.submit(self._poll_health)
        futures["traffic"] = _poll_pool.submit(
            lambda: get_traffic_counters_snmp(self.ip, self.snmp_community) or {}
        )
        if not skip_optical:
            futures["optical"] = _poll_pool.submit(self._poll_optical)
            futures["status"] = _poll_pool.submit(self._poll_status_info)

        # Collect results
        onus, status_map = [], {}
        try:
            onus, status_map = futures["onu_list"].result(timeout=30)
        except Exception as exc:
            logger.warning("Web ONU list scraping failed for %s: %s", self.ip, exc)

        onu_models: Dict[str, str] = {}
        try:
            onu_models = futures["models"].result(timeout=30)
        except Exception as exc:
            logger.warning("Web model scraping failed for %s: %s", self.ip, exc)

        health = {}
        try:
            health = futures["health"].result(timeout=30)
        except Exception as exc:
            logger.warning("Health poll failed for %s: %s", self.ip, exc)

        port_traffic: Dict[int, Dict[str, Any]] = {}
        try:
            port_traffic = futures["traffic"].result(timeout=30)
        except Exception as exc:
            logger.warning("Traffic counter poll failed for %s: %s", self.ip, exc)

        optical: Dict[str, Dict[str, Any]] = {}
        if "optical" in futures:
            try:
                optical = futures["optical"].result(timeout=30)
            except Exception as exc:
                logger.warning("Web OPM scraping failed for %s: %s", self.ip, exc)

        olt_alive_times: Dict[str, Any] = {}
        if "status" in futures:
            try:
                olt_alive_times = futures["status"].result(timeout=30)
            except Exception as exc:
                logger.warning("Web status scraping failed for %s: %s", self.ip, exc)

        return DriverPollResult(
            onus=onus,
            status_map=status_map,
            optical_data=optical,
            onu_models=onu_models,
            olt_alive_times=olt_alive_times,
            health=health,
            port_traffic=port_traffic,
        )
