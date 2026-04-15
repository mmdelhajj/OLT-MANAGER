"""ZTE OLT driver package (Phase 7.5).

Models scaffolded:

- C320 — compact 1U GPON OLT
- C300 — chassis OLT
- C600 — chassis XGS-PON OLT

ZTE uses a different MIB (the C-DATA / ZXAN MIB tree) and Telnet/SSH CLI
commands than VSOL, so a separate base class is required. Real polling
logic to follow as soon as we capture CLI fixtures from a live unit.
"""
