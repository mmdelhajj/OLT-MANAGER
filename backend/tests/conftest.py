"""Pytest fixtures for the OLT driver test suite.

The driver tests need ``backend/`` on ``sys.path`` so they can ``import
olt_drivers`` directly without installing the project. We add it from the
nearest parent that contains the ``olt_drivers`` package.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
