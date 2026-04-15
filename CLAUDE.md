# OLT Manager - Development Notes

## Project Overview
OLT Manager is a web-based management system for GPON/EPON OLT devices. It provides monitoring, configuration, and diagnostics for OLT and ONU devices.

## Current Version
**1.3.105** (February 2026)

## Recent Updates

### v1.3.105 - Real ONU Alive Time from OLT
- Added real ONU uptime from OLT's onustatusinfo.html page
- New field `olt_alive_time` stores OLT-reported alive time in seconds
- Uptime now shows real OLT value (e.g., "6d 22h 49m") instead of our calculated value
- Improved offline reason detection from onustatusinfo.html page:
  - "Last Deregister Reason" field provides: Power Off, Onu Los, etc.
- New web scraper function `get_onu_status_info()` scrapes onustatusinfo.html

### v1.3.104 - Uptime Fix After Reboot
- Fixed uptime not showing after ONU reboot command
- Mark ONU offline when rebooting so polling detects online transition correctly

### v1.3.103 - Manual Poll Bug Fix
- Fixed bug where manual poll would mark all ONUs offline if SNMP returned empty data
- Added protection: skip offline detection if SNMP returns 0 ONUs (likely error, not all deleted)

### v1.3.102 - Uptime Reset on Reboot
- Uptime now resets when ONU reboot command is sent via web interface
- Sets online_since to NULL on reboot, so uptime restarts from 0 when ONU comes back

### v1.3.101/100 - Frontend Deployment Fix
- Fixed nginx serving old frontend from /var/www/html
- Ensured deploy script updates correct directory

### v1.3.99 - Uptime Init Fix
- Fixed uptime tracking for existing online ONUs after upgrade
- online_since now auto-initializes for online ONUs without existing value

### v1.3.98 - ONU Uptime & Offline Reason
- Added ONU uptime tracking (shows "2d 5h 30m" format)
- Added offline reason detection from OLT alarm log:
  - "Power Off" = ONU Dying Gasp alarm (29)
  - "Fiber Cut" = ONU Link LOST alarm (23)
  - "Unknown" = No recent alarm found
- New database fields: online_since (DateTime), offline_reason (String)
- Web scraper parses OLT alarm log page (alarminfo.html) for offline reason

### v1.3.97 - ONU RX Power Fix
- Fixed ONU RX power display to show actual ONU-reported signal (RxOpticalLevelOnu ~-19dBm)
- Previously showed OLT measurement (RxOpticalLevelOlt ~-27dBm) incorrectly
- Web scraper now captures both values:
  - `rx_power` = OLT measures ONU signal (upstream)
  - `onu_rx_power` = ONU measures OLT signal (downstream, what customer sees)

### v1.3.96 - 64-bit SNMP Counters
- Fixed uplink port traffic for high-usage ports using 64-bit counters
- Uses ifHCInOctets/ifHCOutOctets instead of 32-bit ifInOctets/ifOutOctets
- 32-bit counters were wrapping/returning 0 on high-traffic ports

### v1.3.95 - Uplink Traffic Graphs Debug
- Added debug logging for uplink port traffic collection
- Saves GE/XGE traffic to TrafficHistory table

### v1.3.94 - Uplink Port Traffic Graphs
- Added GE/XGE uplink port traffic graphs on dashboard
- Fixed V1600G2-B port mapping: 4 GE ports (1-4) + 4 XGE ports (5-8)
- Traffic now saves to both PortTraffic and TrafficHistory tables

## Architecture

### Backend (Python/FastAPI)
- `main.py` - Main application, API endpoints, polling logic
- `olt_drivers/` - **Driver-based OLT model abstraction** (see below)
- `olt_web_scraper.py` - Web scraping helpers for ONU optical data
- `olt_connector.py` - SNMP helpers for OLT/ONU data
- `models.py` - SQLAlchemy database models

### OLT Driver Architecture (Phase 0 refactor)
Model-specific logic lives in `backend/olt_drivers/` as self-contained driver
classes — **never** as `if 'D8' in model:` branches in `main.py`. Each OLT
model is one Python file inheriting from `OLTDriver` (or a vendor base like
`VSOLDriverBase`). Adding a new OLT model = creating one new file plus one
line in `olt_drivers/registry.py`.

```
backend/olt_drivers/
├── base.py              ← OLTDriver ABC + PortLayout + DriverPollResult
├── registry.py          ← get_driver(olt), get_driver_class(model_string)
└── vsol/
    ├── _base.py         ← VSOLDriverBase: shared VSOL behavior
    ├── v1600d4.py       ← V1600D4 driver
    ├── v1600d8.py       ← V1600D8 driver
    └── v1600g2b.py      ← V1600G2-B driver
```

`olt_connector.py` (SNMP) and `olt_web_scraper.py` (HTTP) are shared utility
libraries that drivers call into — they are **not** model-aware. See
`backend/olt_drivers/README.md` for the full driver interface contract and
step-by-step instructions for adding a new OLT model.

Pytest regression tests live in `backend/tests/` and use `unittest.mock` to
exercise drivers without a real OLT. Run with:

```bash
cd backend && venv/bin/python -m pytest tests/ -v
```

### Frontend (React)
- Located in `/frontend` directory
- Built with React and served by backend

### Database
- SQLite: `data/olt_manager.db`
- Key tables: olts, onus, traffic_history, port_traffic

## Build System
- Uses Nuitka to compile Python to native binary
- Build script: `publish-update.sh`
- Output: Single executable `olt-manager`

## OLT Support
- **VSOL V1600D4** - 4 PON EPON OLT (driver: `olt_drivers/vsol/v1600d4.py`)
- **VSOL V1600D8** - 8 PON EPON OLT (driver: `olt_drivers/vsol/v1600d8.py`)
- **VSOL V1600G2-B** - 16 PON GPON OLT (driver: `olt_drivers/vsol/v1600g2b.py`)

The dropdown of supported models in the UI is fed by
`olt_drivers.registry.list_supported_models()` so drivers are auto-discovered.

## Key OIDs (SNMP)
- Enterprise MIB: 1.3.6.1.4.1.37950 (VSOL)
- 64-bit traffic counters: ifHCInOctets (1.3.6.1.2.1.31.1.1.1.6), ifHCOutOctets (1.3.6.1.2.1.31.1.1.1.10)

## OLT Web Interface Fields
- `RxOpticalLevelOlt` - What OLT measures from ONU (~-27dBm)
- `RxOpticalLevelOnu` - What ONU measures from OLT (~-19dBm)

## OLT Web Interface Pages (for scraping)
- `onuauthinfo.html` - ONU list with status, model, serial
- `onustatusinfo.html` - ONU status with Alive Time, Last Deregister Reason
- `onuopmdiag.html` - ONU optical power diagnostics
- `onuoptical.html` - Individual ONU optical details
- `alarminfo.html` - OLT alarm log (Dying Gasp, Link LOST, etc.)

## Deployment
- Service: `olt-manager.service`
- Default port: 8000 (backend API)
- Install directory: `/opt/olt-manager`
