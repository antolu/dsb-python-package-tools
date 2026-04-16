from __future__ import annotations

import dataclasses
import datetime


@dataclasses.dataclass
class Upgrade:
    dep_name: str
    package_name: str
    datasource: str
    current_version: str
    new_version: str
    update_type: str
    package_file: str
    branch_name: str


@dataclasses.dataclass
class BranchResult:
    branch_name: str
    pr_no: int | None
    pr_title: str
    result: str
    upgrades: list[Upgrade]


@dataclasses.dataclass
class RenovateOutput:
    repository: str
    branches: list[BranchResult]


@dataclasses.dataclass
class BaseDist:
    tag: str
    python: str
    eol: datetime.date
    deprecated: bool = False

    def is_urgent(self, today: datetime.date | None = None) -> bool:
        t = today or datetime.date.today()
        return not self.deprecated and (self.eol - t).days <= 183


@dataclasses.dataclass
class Manifest:
    latest: str
    base_distributions: dict[str, BaseDist]

    def get_base_dist(self, tag: str) -> BaseDist | None:
        return self.base_distributions.get(tag)


@dataclasses.dataclass
class StepContext:
    renovate_output: RenovateOutput | None
    manifest: Manifest
    gitlab_token: str
    dry_run: bool
    repository: str
    gitlab_base: str


class LogParseError(Exception):
    pass


class MaintenanceStep:
    name: str = ""
    requires_renovate_output: bool = False

    def run(self, ctx: StepContext) -> None:
        raise NotImplementedError
