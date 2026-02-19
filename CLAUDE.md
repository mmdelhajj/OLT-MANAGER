# OLT Manager - Development Notes

## Project Overview
OLT Manager is a web-based management system for GPON/EPON OLT devices. It provides monitoring, configuration, and diagnostics for OLT and ONU devices.

## Current Version
**1.3.97** (February 2026)

## Recent Updates

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
- `olt_web_scraper.py` - Web scraping for ONU optical data
- `olt_connector.py` - SNMP polling for OLT/ONU data
- `models.py` - SQLAlchemy database models

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
- **VSOL V1600D8** - 8 PON EPON OLT
- **VSOL V1600G2-B** - 4 GE + 4 XGE GPON OLT

## Key OIDs (SNMP)
- Enterprise MIB: 1.3.6.1.4.1.37950 (VSOL)
- 64-bit traffic counters: ifHCInOctets (1.3.6.1.2.1.31.1.1.1.6), ifHCOutOctets (1.3.6.1.2.1.31.1.1.1.10)

## OLT Web Interface Fields
- `RxOpticalLevelOlt` - What OLT measures from ONU (~-27dBm)
- `RxOpticalLevelOnu` - What ONU measures from OLT (~-19dBm)

## Deployment
- Service: `olt-manager.service`
- Default port: 8000 (backend API)
- Install directory: `/opt/olt-manager`
