"""Shared behavior for all VSOL OLT drivers.

VSOL drivers all talk SNMP via :mod:`olt_connector` and the HTTP web UI via
:mod:`olt_web_scraper`. The shared base implements the management methods
(reboot, delete, descriptions, offline reason) since they look identical
across the VSOL line — only the polling and port layout actually vary by
model.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

from ..base import DriverPollResult, OLTDriver

logger = logging.getLogger(__name__)

# Shared thread pool for parallel poll tasks (one per driver instance is
# wasteful — a single pool with 4 workers suffices since each OLT poll
# runs at most 4 concurrent tasks).
_poll_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="olt-poll")


class VSOLDriverBase(OLTDriver):
    """Common ONU/port management for the VSOL line."""

    VENDOR = "VSOL"

    # ---- ONU management (delegates to olt_web_scraper) ----------------------
    def reboot_onu(self, pon_port: int, onu_id: int) -> bool:
        from olt_web_scraper import reboot_onu_web

        return reboot_onu_web(
            ip=self.ip,
            pon_port=pon_port,
            onu_id=onu_id,
            username=self.web_username,
            password=self.web_password,
            model=self.MODEL,
        )

    def delete_onu(
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> bool:
        from olt_web_scraper import delete_onu_web

        return delete_onu_web(
            ip=self.ip,
            pon_port=pon_port,
            onu_id=onu_id,
            username=self.web_username,
            password=self.web_password,
        )

    def set_onu_description(
        self, pon_port: int, onu_id: int, description: str
    ) -> bool:
        from olt_web_scraper import set_onu_description_web

        return set_onu_description_web(
            ip=self.ip,
            pon_port=pon_port,
            onu_id=onu_id,
            description=description or "",
            username=self.web_username,
            password=self.web_password,
            model=self.MODEL,
        )

    def set_port_description(self, port_number: int, description: str) -> bool:
        from olt_web_scraper import set_port_description_web

        return set_port_description_web(
            ip=self.ip,
            port_number=port_number,
            description=description or "",
            username=self.web_username,
            password=self.web_password,
            model=self.MODEL,
        )

    def get_offline_reason(
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> Optional[str]:
        from olt_web_scraper import get_onu_offline_reason_web

        try:
            return get_onu_offline_reason_web(
                ip=self.ip,
                pon_port=pon_port,
                onu_id=onu_id,
                serial=serial,
                username=self.web_username,
                password=self.web_password,
            )
        except Exception as exc:  # pragma: no cover - best-effort helper
            logger.debug(
                "Could not get offline reason for %s PON %s ONU %s: %s",
                self.ip,
                pon_port,
                onu_id,
                exc,
            )
            return None

    # ---- Parallel poll -------------------------------------------------------
    def poll(self, skip_optical: bool = False) -> DriverPollResult:
        """Run SNMP, optical, health, and traffic polls in parallel.

        When ``skip_optical`` is True the web scrape is skipped entirely —
        the caller uses this to save ~4s on cycles where optical data isn't
        needed (it changes slowly).
        """
        from olt_connector import poll_olt_snmp, get_traffic_counters_snmp

        futures: dict[str, Any] = {}

        # Submit all tasks to the thread pool simultaneously
        futures["snmp"] = _poll_pool.submit(
            lambda: poll_olt_snmp(self.ip, self.snmp_community)
        )
        futures["health"] = _poll_pool.submit(self._poll_health)
        futures["traffic"] = _poll_pool.submit(
            lambda: get_traffic_counters_snmp(self.ip, self.snmp_community) or {}
        )
        if not skip_optical:
            futures["optical"] = _poll_pool.submit(self._poll_optical)

        # Collect results (each with its own error handling)
        onus, status_map = [], {}
        try:
            onus, status_map = futures["snmp"].result(timeout=180)
        except Exception as exc:
            logger.error("SNMP poll failed for %s (%s): %s", self.ip, self.MODEL, exc)

        health = {}
        try:
            health = futures["health"].result(timeout=30)
        except Exception as exc:
            logger.warning("Health poll failed for %s: %s", self.ip, exc)

        port_traffic: Dict[int, Dict[str, Any]] = {}
        try:
            port_traffic = futures["traffic"].result(timeout=180)
        except Exception as exc:
            logger.warning("Traffic counter poll failed for %s: %s", self.ip, exc)

        optical: Dict[str, Dict[str, Any]] = {}
        if "optical" in futures:
            try:
                optical = futures["optical"].result(timeout=30)
            except Exception as exc:
                logger.warning("Web OPM scraping failed for %s: %s", self.ip, exc)

        return DriverPollResult(
            onus=onus,
            status_map=status_map,
            optical_data=optical,
            onu_models={},
            olt_alive_times={},
            health=health,
            port_traffic=port_traffic,
        )

    # ---- Shared poll helpers ------------------------------------------------
    def _poll_health(self) -> Dict[str, Any]:
        """Run the standard health poll for this OLT.

        Wraps :func:`olt_connector.get_olt_health_snmp` so that polling failures
        degrade gracefully (we still return ONU data even if the health probe
        is unavailable).
        """
        from olt_connector import get_olt_health_snmp

        try:
            return (
                get_olt_health_snmp(
                    self.ip, self.snmp_community, num_pon_ports=self.PON_COUNT
                )
                or {}
            )
        except Exception as exc:
            logger.warning("Health poll failed for %s: %s", self.ip, exc)
            return {}

    def _poll_optical(self) -> Dict[str, Dict[str, Any]]:
        """Scrape ONU optical metrics from the OLT web UI."""
        from olt_web_scraper import get_onu_opm_data_web

        try:
            return (
                get_onu_opm_data_web(
                    self.ip, self.web_username, self.web_password
                )
                or {}
            )
        except Exception as exc:
            logger.warning("Web OPM scraping failed for %s: %s", self.ip, exc)
            return {}
