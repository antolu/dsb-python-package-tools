from __future__ import annotations

import datetime
import json
import pathlib
import sys
import urllib.request

from ._types import BaseDist, Manifest


def _parse_manifest_data(data: dict) -> Manifest:
    base_dists: dict[str, BaseDist] = {}
    for tag, entry in data.get("base_distributions", {}).items():
        base_dists[tag] = BaseDist(
            tag=tag,
            python=entry["python"],
            eol=datetime.date.fromisoformat(entry["eol"]),
            deprecated=entry.get("deprecated", False),
        )
    return Manifest(
        latest=data["latest"],
        base_distributions=base_dists,
    )


def _load_from_path(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def _load_from_url(url: str, timeout: int = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def load_manifest(
    url_or_path: str,
    bundled_path: pathlib.Path,
) -> Manifest:
    source = url_or_path
    try:
        if source.startswith(("http://", "https://")):
            data = _load_from_url(source)
        else:
            data = _load_from_path(pathlib.Path(source))
        return _parse_manifest_data(data)
    except Exception as e:
        print(
            f"WARNING: Could not load manifest from {source!r}: {e}. "
            "Falling back to bundled manifest.",
            file=sys.stderr,
        )
        return _parse_manifest_data(_load_from_path(bundled_path))
