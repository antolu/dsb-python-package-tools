from __future__ import annotations

import json
import pathlib

from ._types import BranchResult, LogParseError, RenovateOutput, Upgrade


def parse_log(path: pathlib.Path) -> RenovateOutput:
    if not path.exists():
        msg = f"Log file not found: {path}"
        raise LogParseError(msg)

    branches_entry: dict | None = None
    repository: str | None = None

    try:
        lines = path.read_text().splitlines()
    except OSError as e:
        msg = f"Cannot read log file: {e}"
        raise LogParseError(msg) from e

    if not lines:
        msg = f"Log file is empty: {path}"
        raise LogParseError(msg)

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        try:
            entry = json.loads(stripped_line)
        except json.JSONDecodeError:
            continue
        if entry.get("msg") == "branches info extended":
            branches_entry = entry
            repository = entry.get("repository")

    if branches_entry is None:
        msg = (
            f"No 'branches info extended' entry found in {path}. "
            "Ensure LOG_FORMAT=json and the run completed."
        )
        raise LogParseError(msg)

    branches: list[BranchResult] = []
    for b in branches_entry.get("branchesInformation", []):
        upgrades = [
            Upgrade(
                dep_name=u.get("depName", ""),
                package_name=u.get("packageName", u.get("depName", "")),
                datasource=u.get("datasource", ""),
                current_version=u.get("currentVersion", ""),
                new_version=u.get("newVersion", ""),
                update_type=u.get("updateType", ""),
                package_file=u.get("packageFile", ""),
                branch_name=b.get("branchName", ""),
            )
            for u in b.get("upgrades", [])
        ]
        pr_no_raw = b.get("prNo")
        branches.append(
            BranchResult(
                branch_name=b.get("branchName", ""),
                pr_no=int(pr_no_raw) if pr_no_raw is not None else None,
                pr_title=b.get("prTitle", ""),
                result=b.get("result", ""),
                upgrades=upgrades,
            )
        )

    return RenovateOutput(
        repository=repository or "",
        branches=branches,
    )
