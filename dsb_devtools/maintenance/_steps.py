from __future__ import annotations

from ._types import MaintenanceStep
from .steps.base_dist import BaseDistStep

STEPS: list[MaintenanceStep] = [
    BaseDistStep(),
]
