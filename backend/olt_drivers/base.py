"""Abstract base class for OLT drivers.

Every OLT model driver inherits from :class:`OLTDriver` and implements the
abstract methods. The driver fully owns its model: polling, port layout,
ONU management, and any vendor-specific quirks live inside the driver class.

The shared modules ``olt_connector`` and ``olt_web_scraper`` remain available
as utility libraries — drivers call into them rather than reimplementing
SNMP/HTTP plumbing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Imported lazily inside the methods that need them so that this module can
# be imported without pulling in heavy SNMP/scraping dependencies during
# test collection.


# A 3-tuple describing one physical port:
#   (snmp_if_index, label_shown_in_ui, link_speed)
PortSpec = Tuple[int, str, str]


@dataclass
class PortLayout:
    """Physical port layout for an OLT model.

    Each list contains tuples of ``(if_index, label, speed)``. ``if_index`` is
    the SNMP interface index that the OLT exposes for that port; ``label`` is
    what the dashboard renders (for example ``"GE5"`` or ``"10GE1"``); and
    ``speed`` is a free-form string such as ``"1G"`` or ``"10G"``.
    """

    sfp_ports: List[PortSpec] = field(default_factory=list)
    sfp_plus_ports: List[PortSpec] = field(default_factory=list)
    ge_ports: List[PortSpec] = field(default_factory=list)
    qsfp_ports: List[PortSpec] = field(default_factory=list)
    pon_count: int = 0

    def to_port_mapping(self) -> Dict[int, Tuple[str, int]]:
        """Build the ``if_index -> (port_type, port_number)`` mapping that
        ``main.collect_traffic_history`` uses to attribute uplink counters
        to the right port type.
        """
        mapping: Dict[int, Tuple[str, int]] = {}
        for if_idx, _label, _speed in self.sfp_ports:
            mapping[if_idx] = ("sfp", if_idx)
        for if_idx, _label, _speed in self.sfp_plus_ports:
            mapping[if_idx] = ("xge", if_idx)
        for if_idx, _label, _speed in self.ge_ports:
            mapping[if_idx] = ("ge", if_idx)
        for if_idx, _label, _speed in self.qsfp_ports:
            mapping[if_idx] = ("qsfp", if_idx)
        return mapping


@dataclass
class DriverPollResult:
    """Everything a single ``poll()`` call returns to the caller.

    Fields are intentionally permissive (``Any``/``dict``) so different
    vendors can populate the bits that make sense for their hardware while
    leaving others empty.
    """

    onus: List[Any]                              # List[olt_connector.ONUData]
    status_map: Dict[str, bool]                  # "{pon}:{onu}" -> is_online
    optical_data: Dict[str, Dict[str, Any]]      # MAC or "pon:onu" -> optical
    onu_models: Dict[str, str]                   # "{pon}:{onu}" -> model
    olt_alive_times: Dict[str, Dict[str, Any]]   # "{pon}:{onu}" -> status info
    health: Dict[str, Any]                       # cpu, memory, temp, uptime
    port_traffic: Dict[int, Dict[str, Any]]      # if_index -> rx/tx counters


class OLTDriver(ABC):
    """Abstract base for all OLT model drivers."""

    # ---- Class-level metadata ------------------------------------------------
    VENDOR: str = ""               # e.g. "VSOL"
    MODEL: str = ""                # canonical model code, e.g. "V1600D8"
    DISPLAY_NAME: str = ""         # human-friendly label for dropdowns
    PON_TECH: str = ""             # "EPON" | "GPON" | "XGS-PON" | "XG-PON"
    PON_COUNT: int = 0
    ALIASES: List[str] = []        # alternative model strings
    # False for registered-but-not-yet-working drivers (e.g. Huawei/ZTE stubs
    # whose poll()/actions raise NotImplementedError). Used to warn users at
    # add-time and to grey them out in the model dropdown.
    IMPLEMENTED: bool = True

    # SNMP OID used to read interface names for the uplink port-status poll.
    # Some VSOL models expose readable names through ifName (subtree
    # ``1.3.6.1.2.1.31.1.1.1.1``); others only populate ifDescr
    # (``1.3.6.1.2.1.2.2.1.2``). Override per driver as needed.
    PORT_NAME_OID: str = "1.3.6.1.2.1.2.2.1.2"

    # ---- Construction --------------------------------------------------------
    def __init__(
        self,
        ip: str,
        snmp_community: str = "public",
        web_username: str = "admin",
        web_password: str = "admin",
    ) -> None:
        self.ip = ip
        self.snmp_community = snmp_community or "public"
        self.web_username = web_username or "admin"
        self.web_password = web_password or "admin"

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{self.__class__.__name__} ip={self.ip}>"

    # ---- Resolution ----------------------------------------------------------
    @classmethod
    @abstractmethod
    def matches(cls, model_string: str) -> bool:
        """Return ``True`` if this driver handles the given model string.

        The registry walks driver classes in order and uses the first match.
        Drivers should be defensive and reject ambiguous strings — for example
        the V1600D8 driver must not match ``"V1600D16"``.
        """

    # ---- Polling and metadata ------------------------------------------------
    @abstractmethod
    def poll(self, skip_optical: bool = False) -> DriverPollResult:
        """Perform a full poll cycle for this OLT.

        When ``skip_optical`` is True, the web scrape for optical data
        (RX power, distance, temperature) is skipped to save time — the
        caller only requests optical on every Nth cycle since it changes
        slowly.

        Implementations must populate every field of :class:`DriverPollResult`,
        using empty dicts/lists for data that does not apply to the model.
        """

    @abstractmethod
    def get_port_layout(self) -> PortLayout:
        """Return the static physical port layout for this OLT model."""

    # ---- ONU management ------------------------------------------------------
    @abstractmethod
    def reboot_onu(self, pon_port: int, onu_id: int) -> bool:
        """Reboot a specific ONU. Returns ``True`` on success."""

    @abstractmethod
    def delete_onu(
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> bool:
        """Deauthorize/delete an ONU."""

    @abstractmethod
    def set_onu_description(
        self, pon_port: int, onu_id: int, description: str
    ) -> bool:
        """Set the description (customer name) on the ONU."""

    @abstractmethod
    def set_port_description(self, port_number: int, description: str) -> bool:
        """Set the description on an uplink port."""

    @abstractmethod
    def get_offline_reason(
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> Optional[str]:
        """Return why an ONU is offline (e.g. ``"Power Off"``)."""

    # ---- Optional helpers ----------------------------------------------------
    def get_port_traffic(self) -> Dict[int, Dict[str, Any]]:
        """Default implementation calls the shared SNMP traffic helper."""
        from olt_connector import get_traffic_counters_snmp

        return get_traffic_counters_snmp(self.ip, self.snmp_community)
