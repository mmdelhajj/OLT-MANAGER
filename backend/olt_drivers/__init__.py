"""OLT driver package.

Each OLT model is implemented as a self-contained driver class that knows
how to poll the OLT, render its physical port layout, and execute management
commands (reboot ONU, set descriptions, etc.).

Adding a new OLT model = creating one new driver file under the appropriate
vendor sub-package and registering it in ``registry.py``. Existing drivers
remain untouched.

See ``README.md`` in this directory for the full guide.
"""

from .base import OLTDriver, DriverPollResult, PortLayout
from .registry import (
    get_driver,
    get_driver_class,
    list_supported_models,
    check_model_support,
)

__all__ = [
    "OLTDriver",
    "DriverPollResult",
    "PortLayout",
    "get_driver",
    "get_driver_class",
    "list_supported_models",
    "check_model_support",
]
