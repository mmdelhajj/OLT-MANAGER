"""Shared base class for ZTE ZXAN OLT drivers (Phase 7.5)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from ..base import DriverPollResult, OLTDriver, PortLayout

logger = logging.getLogger(__name__)


class ZTEDriverBase(OLTDriver):
    """Common ZXAN behaviour shared by every ZTE model."""

    VENDOR = "ZTE"
    PORT_NAME_OID = "1.3.6.1.2.1.2.2.1.2"  # ifDescr — ZXAN doesn't populate ifName fully

    DEFAULT_SSH_USER = "zte"
    DEFAULT_SSH_PASS = "zte"

    @contextmanager
    def _zxan_session(self) -> Iterator[Any]:
        """Yield a paramiko channel inside ZXAN privileged config mode."""
        raise NotImplementedError(
            "ZTE ZXAN SSH session not yet implemented — "
            "see docs/vendor-onboarding.md"
        )
        yield None  # pragma: no cover - placeholder

    def poll(self) -> DriverPollResult:  # pragma: no cover - stub
        raise NotImplementedError(
            f"{self.__class__.__name__}.poll() is a Phase 7.5 scaffold."
        )

    def reboot_onu(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int
    ) -> bool:
        raise NotImplementedError("reboot-onu pending ZTE Phase 7.5 implementation")

    def delete_onu(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> bool:
        raise NotImplementedError("delete-onu pending ZTE Phase 7.5 implementation")

    def set_onu_description(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int, description: str
    ) -> bool:
        raise NotImplementedError(
            "set-onu-description pending ZTE Phase 7.5 implementation"
        )

    def set_port_description(  # pragma: no cover - stub
        self, port_number: int, description: str
    ) -> bool:
        raise NotImplementedError(
            "set-port-description pending ZTE Phase 7.5 implementation"
        )

    def get_offline_reason(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> Optional[str]:
        return None

    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        raise NotImplementedError(
            "Subclasses must override get_port_layout() with the model's "
            "physical port specification."
        )
