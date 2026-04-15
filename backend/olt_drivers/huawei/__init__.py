"""Huawei OLT driver package (Phase 7.5).

Models supported (initially as stubs awaiting CLI fixtures from real hardware):

- MA5800 series  → :class:`MA5800Driver`
- MA5683T        → :class:`MA5683TDriver`
- EA5800         → :class:`EA5800Driver`

Each driver inherits from :class:`HuaweiDriverBase` which centralises the
SmartAX SSH session management. Real implementations are added incrementally
as we get access to live OLTs and capture CLI fixtures into
``backend/tests/fixtures/huawei/``.
"""
