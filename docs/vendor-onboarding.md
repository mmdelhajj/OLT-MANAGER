# Adding a New OLT Vendor

This guide describes the workflow for shipping support for a new OLT
vendor (or model). Follow it whenever you add a driver to
`backend/olt_drivers/`.

## Prerequisites

- Access to a real device (or detailed CLI captures from a customer)
- The vendor's MIB file or `display version` SNMP output
- A safe lab environment — never debug against production fiber

## Steps

### 1. Create the package and base class (if new vendor)

```
backend/olt_drivers/<vendor>/
├── __init__.py        # one-line docstring
├── _base.py           # shared SSH/SNMP helpers for the vendor family
└── <model>.py         # one file per model
```

The base class subclasses `OLTDriver` from `backend/olt_drivers/base.py`.
See `huawei/_base.py` and `zte/_base.py` for templates.

### 2. Capture CLI fixtures

In `backend/tests/fixtures/<vendor>/`:

```
ma5800-display-ont-info.txt
ma5800-display-board.txt
ma5800-display-version.txt
```

These are the literal stdout from the CLI commands the driver runs.
**Do not** include any customer-identifying information — strip
hostnames, MAC addresses, and serial numbers before committing.

### 3. Implement the driver

Required `OLTDriver` methods:

| Method                       | What it must do                                       |
|------------------------------|-------------------------------------------------------|
| `matches(model_string)`      | Return True iff this driver handles the model        |
| `poll()`                     | Return a fully populated `DriverPollResult`          |
| `get_port_layout()`          | Return the static `PortLayout` for the model         |
| `reboot_onu(pon, onu)`       | Send the reboot CLI command                          |
| `delete_onu(pon, onu)`       | Deauthorize / delete                                 |
| `set_onu_description(...)`   | Set the customer-facing label                        |
| `set_port_description(...)`  | Set the uplink port label                            |
| `get_offline_reason(...)`    | Look up dying-gasp / fiber-cut from alarm log        |

### 4. Register in `registry.py`

```python
from .vendor.model import VendorModelDriver
_REGISTRY = [
    ...,
    VendorModelDriver,
]
```

Order matters: more specific drivers first. If your driver's `matches`
could collide with another (e.g. ZTE C320 vs C300), add a regression
test in `tests/test_registry.py`.

### 5. Write parser tests

Use `unittest.mock` and the captured CLI fixtures so the tests run
without a real OLT:

```python
def test_ma5800_parses_ont_info():
    fixture = (FIXTURES / "ma5800-display-ont-info.txt").read_text()
    onus = parse_ont_info(fixture)
    assert len(onus) == 64
    assert onus[0].mac == "...."
```

Run: `cd backend && venv/bin/python -m pytest tests/ -v`

### 6. Smoke test against the real device

Once the parser tests pass, point a *staging* OLT row at a real device
and call `/api/olts/{id}/poll/manual`. Capture any divergences as new
fixtures and add regression tests for them.

### 7. Document

- Add the model to the dropdown via `list_supported_models()` (automatic)
- Add a "Setup" page to `docs-site/` with the SSH credentials format and
  any vendor-specific gotchas (default ports, telnet vs ssh, etc.)
- Update `marketing-site/src/pages/features.astro` if it's a milestone

## Don'ts

- Don't add `if 'Vendor X' in model:` branches to `main.py` — that's
  exactly the anti-pattern Phase 0 eliminated
- Don't store credentials in plaintext anywhere; always go through
  `config.encrypt_for_tenant`
- Don't hardcode the IP / community / username in the driver — read
  them from `self.ip`, `self.snmp_community`, etc.
