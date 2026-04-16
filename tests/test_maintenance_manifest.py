from __future__ import annotations

import datetime
import pathlib
from unittest.mock import patch

from dsb_devtools.maintenance._manifest import load_manifest
from dsb_devtools.maintenance._types import Manifest

BUNDLED = (
    pathlib.Path(__file__).parents[1] / "dsb_devtools" / "maintenance" / "manifest.json"
)


def test_load_manifest_from_local_path() -> None:
    m = load_manifest(str(BUNDLED), BUNDLED)
    assert isinstance(m, Manifest)
    assert m.latest == "2026.01"


def test_load_manifest_base_dist_fields() -> None:
    m = load_manifest(str(BUNDLED), BUNDLED)
    dist = m.get_base_dist("2023.06")
    assert dist is not None
    assert dist.python == "3.11"
    assert dist.eol == datetime.date(2027, 12, 1)
    assert not dist.deprecated


def test_load_manifest_deprecated_flag() -> None:
    m = load_manifest(str(BUNDLED), BUNDLED)
    dist = m.get_base_dist("2021.12")
    assert dist is not None
    assert dist.deprecated


def test_load_manifest_unknown_tag_returns_none() -> None:
    m = load_manifest(str(BUNDLED), BUNDLED)
    assert m.get_base_dist("9999.99") is None


def test_load_manifest_falls_back_on_network_error() -> None:
    with patch(
        "dsb_devtools.maintenance._manifest.urllib.request.urlopen"
    ) as mock_open:
        mock_open.side_effect = OSError("network down")
        m = load_manifest("https://example.com/manifest.json", BUNDLED)
    assert m.latest == "2026.01"


def test_load_manifest_falls_back_on_bad_json(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    m = load_manifest(str(bad), BUNDLED)
    assert m.latest == "2026.01"
