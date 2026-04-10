from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

import rich
import survey


@dataclasses.dataclass
class RenovateConfig:
    pyproject: bool = True
    precommit: bool = False
    submodules: bool = False
    pyproject_prefix: str = "chore(deps):"
    precommit_prefix: str = "chore(hooks):"
    submodules_prefix: str = "chore(submodules):"


_GITLAB_BASE = "https://gitlab.cern.ch"
_ACC_PY_REGISTRY = "https://acc-py-repo.cern.ch/repository/vr-py-releases/simple/"
_SSH_URL_RE = re.compile(
    r"^ssh://(?:git@)?gitlab\.cern\.ch(?::\d+)?/(?P<path>.+?)(?:\.git)?$"
)
_HTTPS_URL_RE = re.compile(r"^https://gitlab\.cern\.ch/(?P<path>.+?)(?:\.git)?$")

_SCHEDULE_OPTIONS = ["weekly", "daily", "monthly", "manual only"]
_SCHEDULE_CRONS = {
    "weekly": "0 6 * * 1",
    "daily": "0 6 * * *",
    "monthly": "0 6 1 * *",
    "manual only": None,
}


def _print_ok(msg: str) -> None:
    rich.print(f"[bold green]✓[/bold green] {msg}")


def _print_info(msg: str) -> None:
    rich.print(f"[bold blue].[/bold blue] {msg}")


def _print_err(msg: str) -> None:
    rich.print(f"[bold red]✗[/bold red] {msg}")


def _project_path_from_remote() -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

    for pattern in (_SSH_URL_RE, _HTTPS_URL_RE):
        m = pattern.match(url)
        if m:
            return m.group("path")

    return None


def _api(
    token: str,
    method: str,
    path: str,
    data: dict | None = None,
) -> dict | list:
    url = f"{_GITLAB_BASE}/api/v4{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "PRIVATE-TOKEN": token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        msg = f"GitLab API error {e.code} for {method} {path}: {body_text}"
        raise RuntimeError(msg) from e


def _get_project_id(token: str, project_path: str) -> int:
    encoded = urllib.parse.quote(project_path, safe="")
    result = _api(token, "GET", f"/projects/{encoded}")
    assert isinstance(result, dict)
    return int(result["id"])


def _list_schedules(token: str, project_id: int) -> list[dict]:
    result = _api(token, "GET", f"/projects/{project_id}/pipeline_schedules")
    assert isinstance(result, list)
    return result


def _create_schedule(
    token: str,
    project_id: int,
    cron: str,
    ref: str = "master",
) -> dict:
    result = _api(
        token,
        "POST",
        f"/projects/{project_id}/pipeline_schedules",
        {
            "description": "Renovate dependency updates",
            "ref": ref,
            "cron": cron,
            "cron_timezone": "UTC",
            "active": True,
        },
    )
    assert isinstance(result, dict)
    return result


def _delete_schedule(token: str, project_id: int, schedule_id: int) -> None:
    _api(token, "DELETE", f"/projects/{project_id}/pipeline_schedules/{schedule_id}")


def _set_ci_variable(
    token: str,
    project_id: int,
    key: str,
    value: str,
) -> None:
    existing = _api(token, "GET", f"/projects/{project_id}/variables")
    assert isinstance(existing, list)
    exists = any(v["key"] == key for v in existing)

    if exists:
        _api(
            token,
            "PUT",
            f"/projects/{project_id}/variables/{key}",
            {"value": value, "masked": True, "protected": False},
        )
    else:
        _api(
            token,
            "POST",
            f"/projects/{project_id}/variables",
            {"key": key, "value": value, "masked": True, "protected": False},
        )


def _git_root() -> pathlib.Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return pathlib.Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return pathlib.Path(".")


def _load_renovate_json(cwd: pathlib.Path | None = None) -> RenovateConfig | None:
    p = (cwd or _git_root()) / "renovate.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    cfg = RenovateConfig()
    enabled = set(data.get("enabledManagers", []))
    cfg.pyproject = "pep621" in enabled
    cfg.precommit = "pre-commit" in enabled
    cfg.submodules = "git-submodules" in enabled

    for rule in data.get("packageRules", []):
        match_managers = rule.get("matchManagers", [])
        prefix = rule.get("commitMessagePrefix")
        if not prefix:
            continue
        if "pep621" in match_managers:
            cfg.pyproject_prefix = prefix
        if "pre-commit" in match_managers:
            cfg.precommit_prefix = prefix
        if "gitSubmodules" in match_managers:
            cfg.submodules_prefix = prefix

    return cfg


def _detect_has_submodules(cwd: pathlib.Path | None = None) -> bool:
    p = (cwd or _git_root()) / ".gitmodules"
    return p.exists() and p.stat().st_size > 0


def _detect_has_precommit(cwd: pathlib.Path | None = None) -> bool:
    p = (cwd or _git_root()) / ".pre-commit-config.yaml"
    return p.exists()


def write_renovate_json(
    config: RenovateConfig,
    dest: pathlib.Path | None = None,
) -> None:
    enabled_managers = []
    if config.pyproject:
        enabled_managers.append("pep621")
    if config.submodules:
        enabled_managers.append("git-submodules")
    if config.precommit:
        enabled_managers.append("pre-commit")

    package_rules: list[dict] = [
        {"matchDatasources": ["python-version"], "enabled": False},
    ]
    if config.pyproject:
        package_rules.append({
            "matchManagers": ["pep621"],
            "commitMessagePrefix": config.pyproject_prefix,
        })
    if config.precommit:
        package_rules.append({
            "matchManagers": ["pre-commit"],
            "commitMessagePrefix": config.precommit_prefix,
        })
    if config.submodules:
        package_rules.append({
            "matchManagers": ["git-submodules"],
            "versioning": "semver",
            "commitMessagePrefix": config.submodules_prefix,
        })

    payload: dict = {
        "$schema": "https://docs.renovatebot.com/renovate-schema.json",
        "extends": ["config:base"],
        "automerge": False,
        "enabledManagers": enabled_managers,
        "pypi": {"registryUrls": [_ACC_PY_REGISTRY]},
    }
    if config.pyproject:
        payload["pep621"] = {"managerFilePatterns": ["/(^|/)pyproject\\.toml$/"]}
    if package_rules:
        payload["packageRules"] = package_rules

    out = (dest or pathlib.Path(".")) / "renovate.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    _print_ok(f"Written {out}")


def _prompt_renovate_config(
    default: RenovateConfig | None = None,
    cwd: pathlib.Path | None = None,
) -> RenovateConfig:
    cfg = default or RenovateConfig()
    has_submodules = _detect_has_submodules(cwd)
    has_precommit = _detect_has_precommit(cwd)

    cfg.pyproject = survey.routines.inquire(
        "Renovate: manage pyproject.toml dependencies? ", default=cfg.pyproject
    )
    if cfg.pyproject:
        cfg.pyproject_prefix = survey.routines.input(
            "Renovate: commit prefix for pyproject updates? ",
            value=cfg.pyproject_prefix,
        )
    if has_precommit:
        cfg.precommit = survey.routines.inquire(
            "Renovate: manage pre-commit hook revisions? ", default=cfg.precommit
        )
        if cfg.precommit:
            cfg.precommit_prefix = survey.routines.input(
                "Renovate: commit prefix for pre-commit updates? ",
                value=cfg.precommit_prefix,
            )
    if has_submodules:
        cfg.submodules = survey.routines.inquire(
            "Renovate: manage git submodule tags? ", default=cfg.submodules
        )
        if cfg.submodules:
            cfg.submodules_prefix = survey.routines.input(
                "Renovate: commit prefix for submodule updates? ",
                value=cfg.submodules_prefix,
            )

    return cfg


def _resolve_project_path(project_path: str | None) -> str:
    if project_path:
        return project_path

    detected = _project_path_from_remote()
    if detected:
        _print_info(f"Detected project from git remote: {detected}")
        if survey.routines.inquire(f"Use {detected}? ", default=True):
            return detected

    return survey.routines.input("GitLab project path (e.g. dsb/devops/myrepo): ")


def _resolve_token(token: str | None) -> str:
    if token:
        return token

    env_token = os.environ.get("RENOVATE_TOKEN") or os.environ.get("GITLAB_TOKEN")
    if env_token:
        _print_info("Using token from environment (RENOVATE_TOKEN / GITLAB_TOKEN)")
        return env_token

    return survey.routines.input(
        "GitLab access token (scopes: api, read_repository, write_repository): ",
    )


def setup(
    project_path: str | None = None,
    token: str | None = None,
    renovate_config: RenovateConfig | None = None,
    dest: pathlib.Path | None = None,
    *,
    set_token_var: bool = True,
) -> None:
    renovate_config = _prompt_renovate_config(default=renovate_config, cwd=dest)
    write_renovate_json(renovate_config, dest=dest)

    token = _resolve_token(token)
    project_path = _resolve_project_path(project_path)

    try:
        project_id = _get_project_id(token, project_path)
    except RuntimeError as e:
        _print_err(f"Could not access project: {e}")
        sys.exit(1)

    _print_ok(f"Project {project_path} found (id={project_id})")

    if set_token_var:
        _print_info("Setting RENOVATE_TOKEN CI variable...")
        try:
            _set_ci_variable(token, project_id, "RENOVATE_TOKEN", token)
            _print_ok("RENOVATE_TOKEN CI variable set (masked)")
        except RuntimeError as e:
            _print_err(f"Failed to set CI variable: {e}")
            sys.exit(1)

    schedule_choice = _SCHEDULE_OPTIONS[
        survey.routines.select(
            "How often should Renovate run? ",
            options=_SCHEDULE_OPTIONS,
        )
    ]

    cron = _SCHEDULE_CRONS[schedule_choice]
    if cron:
        try:
            sched = _create_schedule(token, project_id, cron)
            _print_ok(
                f"Schedule created: {schedule_choice} (cron: {cron}, id={sched['id']})"
            )
        except RuntimeError as e:
            _print_err(f"Failed to create schedule: {e}")
            sys.exit(1)
    else:
        _print_ok("No schedule created — trigger the renovate job manually in CI")


def teardown(
    project_path: str | None = None,
    token: str | None = None,
) -> None:
    token = _resolve_token(token)
    project_path = _resolve_project_path(project_path)

    try:
        project_id = _get_project_id(token, project_path)
    except RuntimeError as e:
        _print_err(f"Could not access project: {e}")
        sys.exit(1)

    schedules = _list_schedules(token, project_id)
    renovate_schedules = [
        s for s in schedules if "renovate" in s["description"].lower()
    ]

    if not renovate_schedules:
        _print_info("No Renovate schedules found")
    else:
        for sched in renovate_schedules:
            if survey.routines.inquire(
                f"Delete schedule '{sched['description']}' (cron: {sched['cron']}, id={sched['id']})? ",
                default=True,
            ):
                try:
                    _delete_schedule(token, project_id, sched["id"])
                    _print_ok(f"Deleted schedule id={sched['id']}")
                except RuntimeError as e:
                    _print_err(f"Failed to delete schedule: {e}")

    if survey.routines.inquire("Remove RENOVATE_TOKEN CI variable? ", default=False):
        try:
            _api(token, "DELETE", f"/projects/{project_id}/variables/RENOVATE_TOKEN")
            _print_ok("RENOVATE_TOKEN CI variable removed")
        except RuntimeError as e:
            _print_err(f"Failed to remove CI variable: {e}")


def update(
    project_path: str | None = None,
    token: str | None = None,
) -> None:
    token = _resolve_token(token)
    project_path = _resolve_project_path(project_path)

    try:
        project_id = _get_project_id(token, project_path)
    except RuntimeError as e:
        _print_err(f"Could not access project: {e}")
        sys.exit(1)

    schedules = _list_schedules(token, project_id)
    renovate_schedules = [
        s for s in schedules if "renovate" in s["description"].lower()
    ]

    existing_config = _load_renovate_json()
    if existing_config:
        _print_info("Loaded existing renovate.json as defaults")

    if not renovate_schedules:
        _print_info("No existing Renovate schedules found — creating one")
        setup(
            project_path=project_path,
            token=token,
            renovate_config=existing_config,
            set_token_var=False,
        )
        return

    renovate_config = _prompt_renovate_config(default=existing_config)
    write_renovate_json(renovate_config)

    for sched in renovate_schedules:
        _print_info(
            f"Existing schedule id={sched['id']}: cron={sched['cron']}, active={sched['active']}"
        )
        schedule_choice = _SCHEDULE_OPTIONS[
            survey.routines.select(
                "New schedule? ",
                options=_SCHEDULE_OPTIONS,
            )
        ]
        cron = _SCHEDULE_CRONS[schedule_choice]
        if cron:
            _api(
                token,
                "PUT",
                f"/projects/{project_id}/pipeline_schedules/{sched['id']}",
                {"cron": cron, "cron_timezone": "UTC"},
            )
            _print_ok(
                f"Updated schedule id={sched['id']} to {schedule_choice} ({cron})"
            )
        else:
            _delete_schedule(token, project_id, sched["id"])
            _print_ok(f"Removed schedule id={sched['id']} (manual only)")


def make_parser(
    main_parser: argparse.ArgumentParser | None = None,
) -> argparse.ArgumentParser:
    parser = main_parser or argparse.ArgumentParser(
        description="Manage Renovate CI setup for a GitLab project."
    )
    parser.add_argument(
        "--project",
        dest="project_path",
        type=str,
        default=None,
        help="GitLab project path (e.g. dsb/devops/myrepo). Auto-detected from git remote if omitted.",
    )
    parser.add_argument(
        "--token",
        dest="token",
        type=str,
        default=None,
        help="GitLab access token. Falls back to RENOVATE_TOKEN / GITLAB_TOKEN env vars.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "setup", help="Set up Renovate CI schedule and token variable"
    )
    subparsers.add_parser(
        "teardown", help="Remove Renovate CI schedule and token variable"
    )
    subparsers.add_parser("update", help="Update existing Renovate CI schedule")

    return parser


def main(
    argv: list[str] | None = None,
    parser: argparse.ArgumentParser | None = None,
) -> None:
    argv = argv or sys.argv[1:]
    parser = make_parser(main_parser=parser)
    args = parser.parse_args(argv)

    try:
        if args.command == "setup":
            setup(project_path=args.project_path, token=args.token)
        elif args.command == "teardown":
            teardown(project_path=args.project_path, token=args.token)
        elif args.command == "update":
            update(project_path=args.project_path, token=args.token)
    except KeyboardInterrupt:
        _print_ok("\nAborted")
        sys.exit(0)
