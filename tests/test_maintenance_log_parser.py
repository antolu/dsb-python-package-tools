from __future__ import annotations

import datetime
import pathlib

import pytest

from dsb_devtools.maintenance._log_parser import parse_log
from dsb_devtools.maintenance._types import BaseDist, LogParseError, RenovateOutput


def test_is_urgent_within_six_months() -> None:
    today = datetime.date(2026, 10, 1)
    dist = BaseDist(tag="2023.06", python="3.11", eol=datetime.date(2027, 1, 1))
    assert dist.is_urgent(today=today)


def test_is_urgent_more_than_six_months() -> None:
    today = datetime.date(2026, 4, 1)
    dist = BaseDist(tag="2023.06", python="3.11", eol=datetime.date(2027, 4, 1))
    assert not dist.is_urgent(today=today)


def test_is_urgent_deprecated_is_never_urgent() -> None:
    today = datetime.date(2026, 4, 1)
    dist = BaseDist(
        tag="2021.12", python="3.9", eol=datetime.date(2026, 12, 1), deprecated=True
    )
    assert not dist.is_urgent(today=today)


FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "renovate_sa_preisach.log"


def test_parse_log_returns_renovate_output() -> None:
    result = parse_log(FIXTURE)
    assert isinstance(result, RenovateOutput)


def test_parse_log_repository() -> None:
    result = parse_log(FIXTURE)
    assert result.repository == "dsb/hysteresis/sa-preisach"


def test_parse_log_branches() -> None:
    result = parse_log(FIXTURE)
    branch_names = {b.branch_name for b in result.branches}
    assert "renovate/numpy-2.x" in branch_names
    assert "renovate/pandas-3.x" in branch_names
    assert "renovate/setuptools-scm-10.x" in branch_names


def test_parse_log_upgrade_fields() -> None:
    result = parse_log(FIXTURE)
    numpy_branch = next(
        b for b in result.branches if b.branch_name == "renovate/numpy-2.x"
    )
    assert len(numpy_branch.upgrades) == 1
    u = numpy_branch.upgrades[0]
    assert u.dep_name == "numpy"
    assert u.current_version == "1.26.4"
    assert u.new_version == "2.4.4"
    assert u.update_type == "major"
    assert u.datasource == "pypi"
    assert u.package_file == "pyproject.toml"


def test_parse_log_pr_no_is_none_in_dry_run() -> None:
    result = parse_log(FIXTURE)
    for branch in result.branches:
        assert branch.pr_no is None


def test_parse_log_missing_file_raises() -> None:
    with pytest.raises(LogParseError):
        parse_log(pathlib.Path("does_not_exist.log"))


def test_parse_log_empty_file_raises(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "empty.log"
    p.write_text("")
    with pytest.raises(LogParseError):
        parse_log(p)
