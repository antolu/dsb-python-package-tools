from __future__ import annotations

import pathlib
import re
import sys
import urllib.parse
import urllib.request

import rich

from .._types import MaintenanceStep, StepContext

_TAG_RE = re.compile(r'ACC_PY_BASE_IMAGE_TAG:\s*["\']?(?P<tag>[\d.]+)["\']?')


def _read_base_tag_from_file(path: pathlib.Path) -> str | None:
    text = path.read_text()
    m = _TAG_RE.search(text)
    return m.group("tag") if m else None


def _read_base_tag_from_api(
    token: str, gitlab_base: str, repository: str
) -> str | None:
    encoded = urllib.parse.quote(repository, safe="")
    encoded_file = urllib.parse.quote(".gitlab-ci.yml", safe="")
    url = f"{gitlab_base}/api/v4/projects/{encoded}/repository/files/{encoded_file}/raw?ref=HEAD"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode()
        m = _TAG_RE.search(content)
        return m.group("tag") if m else None
    except (OSError, urllib.error.URLError) as e:
        rich.print(
            f"[bold red]✗[/bold red] Could not fetch .gitlab-ci.yml: {e}",
            file=sys.stderr,
        )
        return None


class BaseDistStep(MaintenanceStep):
    name = "base-dist"
    requires_renovate_output = False

    def __init__(self, ci_yml_path: pathlib.Path | None = None) -> None:
        self._ci_yml_path = ci_yml_path

    def run(self, ctx: StepContext) -> None:
        if self._ci_yml_path is not None:
            tag = _read_base_tag_from_file(self._ci_yml_path)
        elif ctx.dry_run:
            rich.print(
                "[bold yellow]![/bold yellow] base-dist: no ci_yml_path in dry-run, skipping",
                file=sys.stderr,
            )
            return
        else:
            tag = _read_base_tag_from_api(
                ctx.gitlab_token, ctx.gitlab_base, ctx.repository
            )

        if tag is None:
            rich.print(
                "[bold yellow]![/bold yellow] base-dist: ACC_PY_BASE_IMAGE_TAG not found",
                file=sys.stderr,
            )
            return

        dist = ctx.manifest.get_base_dist(tag)
        if dist is None:
            rich.print(
                f"[bold yellow]![/bold yellow] base-dist: tag {tag!r} not in manifest",
                file=sys.stderr,
            )
            return

        if dist.deprecated:
            rich.print(
                f"[bold red]DEPRECATED[/bold red] Base distribution {tag} "
                f"(Python {dist.python}) is deprecated. EOL: {dist.eol}. "
                f"Please upgrade to {ctx.manifest.latest}."
            )
        elif dist.is_urgent():
            rich.print(
                f"[bold yellow]URGENT[/bold yellow] Base distribution {tag} "
                f"(Python {dist.python}) reaches EOL on {dist.eol} (within 6 months). "
                f"Please plan upgrade to {ctx.manifest.latest}."
            )
