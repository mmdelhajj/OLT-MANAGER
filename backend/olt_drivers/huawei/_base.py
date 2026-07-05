"""Shared base class for Huawei SmartAX OLT drivers (Phase 7.5).

Huawei OLTs do not expose enough functionality through SNMP for our use
case, so the driver primarily speaks the SmartAX CLI over SSH. This base
class manages the SSH session and provides the helpers every Huawei
model needs.

Real polling logic is intentionally NOT implemented yet — see
``poll()`` in each model file. The scaffold lets us register the
drivers in the registry and ship the dropdown for vendor selection
without shipping half-implemented hardware code.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from ..base import DriverPollResult, OLTDriver, PortLayout

logger = logging.getLogger(__name__)


class HuaweiDriverBase(OLTDriver):
    """Common SmartAX behaviour shared by every Huawei model."""

    VENDOR = "Huawei"
    IMPLEMENTED = False  # stub: poll()/actions raise NotImplementedError (pending Phase 7.5)
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"  # Huawei does populate ifName

    # SSH credentials default to "root/admin123" which Huawei ships with;
    # real customers must change them and we read the override from the
    # encrypted OLT row.
    DEFAULT_SSH_USER = "root"
    DEFAULT_SSH_PASS = "admin123"

    # ------------------------------------------------------------------
    # SSH session helper
    # ------------------------------------------------------------------
    @contextmanager
    def _smartax_session(self) -> Iterator[Any]:
        """Yield a paramiko channel ready to issue SmartAX commands.

        Real implementation will:
            1. Open an SSH connection
            2. Send `enable`, then `config`
            3. Set terminal length 0 so output isn't paginated
            4. Yield the interactive channel
            5. On exit, send `quit` and close the connection

        Right now this is a NotImplementedError stub so any code path
        that tries to talk to a real Huawei OLT fails loudly until the
        implementation lands.
        """
        raise NotImplementedError(
            "Huawei SmartAX SSH session not yet implemented — "
            "see docs/vendor-onboarding.md"
        )
        yield None  # pragma: no cover - placeholder for type checker

    def _run_command(self, cmd: str) -> str:
        """Run a single CLI command in a fresh session and return stdout."""
        with self._smartax_session() as chan:  # pragma: no cover - stub
            chan.send(cmd + "\n")
            return chan.recv(65535).decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # OLTDriver contract — generic stubs that subclasses can override.
    # ------------------------------------------------------------------
    def poll(self) -> DriverPollResult:  # pragma: no cover - stub
        raise NotImplementedError(
            f"{self.__class__.__name__}.poll() is a Phase 7.5 scaffold; "
            "needs real CLI parsing fixtures before it can run."
        )

    def reboot_onu(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int
    ) -> bool:
        raise NotImplementedError(
            "reboot-onu translates to `interface gpon 0/<frame>/<slot>; "
            "ont reset <pon> <onu>` — pending fixture capture."
        )

    def delete_onu(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> bool:
        raise NotImplementedError("delete-onu pending Phase 7.5 implementation")

    def set_onu_description(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int, description: str
    ) -> bool:
        raise NotImplementedError(
            "set-onu-description pending Phase 7.5 implementation"
        )

    def set_port_description(  # pragma: no cover - stub
        self, port_number: int, description: str
    ) -> bool:
        raise NotImplementedError(
            "set-port-description pending Phase 7.5 implementation"
        )

    def get_offline_reason(  # pragma: no cover - stub
        self, pon_port: int, onu_id: int, serial: Optional[str] = None
    ) -> Optional[str]:
        # Huawei alarm log scraping is the eventual implementation.
        return None

    # PortLayout is metadata only and doesn't need a live OLT to populate,
    # so subclasses can return real layouts without the SSH stub blocking.
    def get_port_layout(self) -> PortLayout:  # pragma: no cover - stub
        raise NotImplementedError(
            "Subclasses must override get_port_layout() with the model's "
            "physical port specification."
        )
