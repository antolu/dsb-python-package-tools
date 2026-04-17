from __future__ import annotations

from ._types import MaintenanceStep
from .steps.base_dist import BaseDistStep
from .steps.setup_py import SetupPyStep

STEPS: list[MaintenanceStep] = [
    BaseDistStep(),
    SetupPyStep(),
]
