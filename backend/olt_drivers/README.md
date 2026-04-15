# OLT Driver Package

This package contains the model-specific drivers that OLT Manager uses to talk
to the supported OLT hardware. The goal of the package is simple:

> **Adding support for a new OLT model = creating one new file.**
>
> Existing drivers must remain untouched and unbreakable.

`main.py` no longer contains `if 'D8' in model:` / `elif 'G2' in model:` chains.
Instead, every code path that needs model-specific behavior calls into a driver:

```python
from olt_drivers import get_driver

driver = get_driver(olt)               # resolves model -> driver instance
result = driver.poll()                  # full SNMP/web poll cycle
layout = driver.get_port_layout()       # physical port layout for the dashboard
driver.reboot_onu(pon_port, onu_id)     # ONU management
```

`olt_connector.py` (SNMP) and `olt_web_scraper.py` (HTTP) are still the shared
plumbing libraries. Drivers call into them; they do **not** reimplement SNMP
walks or HTML parsing.

---

## Layout

```
backend/olt_drivers/
├── __init__.py          ← public exports
├── base.py              ← OLTDriver ABC, PortLayout, DriverPollResult
├── registry.py          ← get_driver(olt), get_driver_class(model_string)
├── README.md            ← this file
└── vsol/
    ├── __init__.py
    ├── _base.py         ← VSOLDriverBase: shared VSOL behavior
    ├── v1600d4.py       ← V1600D4 driver (4 PON EPON)
    ├── v1600d8.py       ← V1600D8 driver (8 PON EPON)
    └── v1600g2b.py      ← V1600G2-B driver (16 PON GPON)
```

---

## How a driver is resolved

```
olt.model = "V1600D8"
                │
                ▼
   registry._REGISTRY = [V1600G2BDriver, V1600D8Driver, V1600D4Driver]
                │
                ▼
   for cls in _REGISTRY:
       if cls.matches(model):
           return cls
```

Order matters: more specific drivers are listed **first**. The registry uses
the first match — so the V1600G2-B driver is checked before any generic
"V1600" matcher could falsely claim it.

Each driver's `matches()` method must be **defensively narrow**: the V1600D8
driver explicitly rejects `V1600D16` and `V1600D-MINI` so that adding those
models later cannot break it.

---

## How to add a new driver

The example below adds a hypothetical `V1600D16` (16 PON EPON OLT) driver.

### 1. Create the driver file

```python
# backend/olt_drivers/vsol/v1600d16.py
"""VSOL V1600D16 driver — 16 PON EPON OLT."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..base import DriverPollResult, PortLayout
from ._base import VSOLDriverBase

logger = logging.getLogger(__name__)


class V1600D16Driver(VSOLDriverBase):
    MODEL = "V1600D16"
    DISPLAY_NAME = "VSOL V1600D16 (16 PON EPON)"
    PON_TECH = "EPON"
    PON_COUNT = 16
    ALIASES = ["V1600D16", "1600D16"]
    PORT_NAME_OID = "1.3.6.1.2.1.31.1.1.1.1"  # ifName

    @classmethod
    def matches(cls, model_string: str) -> bool:
        if not model_string:
            return False
        m = model_string.upper()
        # Be defensive — never match a sibling model.
        if "D-MINI" in m:
            return False
        return "D16" in m

    def poll(self) -> DriverPollResult:
        from olt_connector import poll_olt_snmp, get_traffic_counters_snmp

        try:
            onus, status_map = poll_olt_snmp(self.ip, self.snmp_community)
        except Exception as exc:
            logger.error("SNMP poll failed for %s: %s", self.ip, exc)
            onus, status_map = [], {}

        return DriverPollResult(
            onus=onus,
            status_map=status_map,
            optical_data=self._poll_optical(),
            onu_models={},
            olt_alive_times={},
            health=self._poll_health(),
            port_traffic=get_traffic_counters_snmp(self.ip, self.snmp_community) or {},
        )

    def get_port_layout(self) -> PortLayout:
        # Adjust to match the actual front-panel layout.
        return PortLayout(
            sfp_ports=[(i, f"GE{i}", "1G") for i in range(1, 5)],
            sfp_plus_ports=[(i, f"GE{i}", "10G") for i in range(5, 9)],
            ge_ports=[(i, f"GE{i}", "1G") for i in range(9, 17)],
            qsfp_ports=[],
            pon_count=self.PON_COUNT,
        )
```

`VSOLDriverBase` already implements `reboot_onu`, `delete_onu`,
`set_onu_description`, `set_port_description`, and `get_offline_reason` by
delegating to the shared `olt_web_scraper` helpers, so you only have to override
those if your model needs vendor-specific behavior.

### 2. Register it

```python
# backend/olt_drivers/registry.py
from .vsol.v1600d16 import V1600D16Driver

_REGISTRY: List[Type[OLTDriver]] = [
    V1600G2BDriver,    # most specific first
    V1600D16Driver,    # ← new driver, listed BEFORE V1600D8 because "D16" is more specific
    V1600D8Driver,
    V1600D4Driver,
]
```

### 3. Add tests

Create `backend/tests/test_vsol_v1600d16_parser.py` modeled on
`test_vsol_v1600d8_parser.py`. Use `unittest.mock.patch` to stub
`olt_connector.poll_olt_snmp`, `olt_connector.get_olt_health_snmp`,
`olt_connector.get_traffic_counters_snmp` and `olt_web_scraper.*` — no real
OLT is needed.

At a minimum cover:

- `test_v1600d16_metadata` — verifies `MODEL`, `PON_TECH`, `PON_COUNT`
- `test_v1600d16_matches` — accepts canonical strings, rejects siblings
- `test_v1600d16_port_layout` — verifies SFP/SFP+/RJ45 if-indexes
- `test_v1600d16_poll_uses_subtree12_snmp_helper` — driver calls into
  `poll_olt_snmp` and populates `DriverPollResult` correctly
- `test_v1600d16_poll_degrades_when_snmp_fails` — never raises on a failing
  SNMP call

Then run:

```bash
cd backend
venv/bin/python -m pytest tests/ -v
```

All existing drivers' tests **must still pass**. If they do, your new driver
is fully isolated from the rest of the codebase.

### 4. Check there's nothing else to do

There isn't. `main.py` calls `get_driver(olt)` and consumes whatever
`PortLayout` / `DriverPollResult` your driver returns — it has no idea what
model the OLT is. The dashboard's "supported models" dropdown is fed by
`list_supported_models()`, which auto-discovers your driver from the registry.

---

## Driver interface contract

Every driver must implement:

| Method                          | Returns               | Notes                                        |
|---------------------------------|-----------------------|----------------------------------------------|
| `matches(model_string)`         | `bool` (classmethod)  | Defensive — must reject sibling models       |
| `poll()`                        | `DriverPollResult`    | Never raise; degrade with empty fields       |
| `get_port_layout()`             | `PortLayout`          | Static — no I/O                              |
| `reboot_onu(pon, onu)`          | `bool`                |                                              |
| `delete_onu(pon, onu, serial)`  | `bool`                |                                              |
| `set_onu_description(...)`      | `bool`                |                                              |
| `set_port_description(...)`     | `bool`                |                                              |
| `get_offline_reason(...)`       | `Optional[str]`       | e.g. `"Power Off"`, `"Onu Los"`              |

Class metadata every driver must set:

| Attribute        | Example                               |
|------------------|---------------------------------------|
| `VENDOR`         | `"VSOL"` (inherited from VSOLDriverBase) |
| `MODEL`          | `"V1600D8"`                           |
| `DISPLAY_NAME`   | `"VSOL V1600D8 (8 PON EPON)"`         |
| `PON_TECH`       | `"EPON"` / `"GPON"` / `"XGS-PON"` / `"XG-PON"` |
| `PON_COUNT`      | `8`                                   |
| `ALIASES`        | `["V1600D8", "1600D8"]`               |
| `PORT_NAME_OID`  | `"1.3.6.1.2.1.31.1.1.1.1"` (ifName) or `"1.3.6.1.2.1.2.2.1.2"` (ifDescr) |

---

## Why drivers and not vendor SDKs?

- **Zero friction.** Adding an OLT is one file + one line in the registry.
- **No cross-contamination.** A bug in the V1600D16 driver cannot break the
  V1600D8 driver — they share nothing but the abstract base class.
- **Trivial to test.** Drivers are pure Python objects with no global state,
  so `unittest.mock.patch` is enough to exercise them. No real OLT or fixture
  files are required.
- **Vendor-agnostic from day one.** When Huawei/ZTE/Fiberhome support is
  added (Phase 7), they live in `olt_drivers/huawei/`, `olt_drivers/zte/` and
  `olt_drivers/fiberhome/` subpackages — same registry, same interface.

---

## Running the tests

```bash
cd backend
venv/bin/python -m pytest tests/ -v
```

Currently 47 tests cover the 3 production drivers and the registry. The
target is to keep test runtime under one second so the suite can run on every
file save during development.
