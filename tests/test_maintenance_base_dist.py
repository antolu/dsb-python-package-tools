from __future__ import annotations

import datetime
import pathlib
from unittest.mock import patch

import pytest

from dsb_devtools.maintenance._types import BaseDist, Manifest, StepContext
from dsb_devtools.maintenance.steps.base_dist import (
    BaseDistStep,
    _read_base_tag_from_file,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _make_manifest() -> Manifest:
    return Manifest(
        latest="2026.01",
        base_distributions={
            "2026.01": BaseDist(
                tag="2026.01", python="3.14", eol=datetime.date(2031, 1, 1)
            ),
            "2023.06": BaseDist(
                tag="2023.06", python="3.11", eol=datetime.date(2027, 12, 1)
            ),
            "2021.12": BaseDist(
                tag="2021.12",
                python="3.9",
                eol=datetime.date(2026, 12, 1),
                deprecated=True,
            ),
            "2020.11": BaseDist(
                tag="2020.11",
                python="3.7",
                eol=datetime.date(2026, 12, 1),
                deprecated=True,
            ),
        },
    )


def _make_ctx() -> StepContext:
    return StepContext(
        renovate_output=None,
        manifest=_make_manifest(),
        gitlab_token="tok",
        dry_run=True,
        repository="org/repo",
        gitlab_base="https://gitlab.cern.ch",
    )


def test_read_base_tag_from_file_parses_tag() -> None:
    tag = _read_base_tag_from_file(FIXTURES / "gitlab_ci_2023.06.yml")
    assert tag == "2023.06"


def test_read_base_tag_from_file_latest() -> None:
    tag = _read_base_tag_from_file(FIXTURES / "gitlab_ci_2026.01.yml")
    assert tag == "2026.01"


def test_base_dist_step_no_warning_for_current(capsys: pytest.CaptureFixture) -> None:
    step = BaseDistStep(ci_yml_path=FIXTURES / "gitlab_ci_2026.01.yml")
    step.run(_make_ctx())
    captured = capsys.readouterr()
    assert "deprecated" not in captured.out.lower()
    assert "urgent" not in captured.out.lower()


def test_base_dist_step_warns_deprecated(capsys: pytest.CaptureFixture) -> None:
    step = BaseDistStep(ci_yml_path=FIXTURES / "gitlab_ci_2021.12.yml")
    step.run(_make_ctx())
    captured = capsys.readouterr()
    combined = (captured.out + captured.err).lower()
    assert "deprecated" in combined


def test_base_dist_step_warns_urgent(capsys: pytest.CaptureFixture) -> None:
    step = BaseDistStep(ci_yml_path=FIXTURES / "gitlab_ci_2023.06.yml")
    # 2023.06 eol=2027-12-01, patch today to be within 6 months
    with patch("dsb_devtools.maintenance._types.datetime") as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2027, 8, 1)
        mock_dt.date.fromisoformat = datetime.date.fromisoformat
        step.run(_make_ctx())
    captured = capsys.readouterr()
    combined = (captured.out + captured.err).lower()
    assert "urgent" in combined
