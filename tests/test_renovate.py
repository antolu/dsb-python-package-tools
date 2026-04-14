from __future__ import annotations

import json
import pathlib
import subprocess
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from dsb_devtools.renovate._renovate import (
    _api,
    _ensure_renovate_ci_include,
    _ensure_renovate_ci_job_entry,
    _get_project_id,
    _project_path_from_remote,
    _set_ci_variable,
    _write_renovate_ci_template,
    ensure_renovate_ci_job,
    make_parser,
)

# --- URL parsing ---


@pytest.mark.parametrize(
    ("remote_url", "expected"),
    [
        (
            "ssh://git@gitlab.cern.ch:7999/dsb/devops/myrepo.git",
            "dsb/devops/myrepo",
        ),
        (
            "ssh://gitlab.cern.ch/dsb/devops/myrepo.git",
            "dsb/devops/myrepo",
        ),
        (
            "https://gitlab.cern.ch/dsb/devops/myrepo.git",
            "dsb/devops/myrepo",
        ),
        (
            "https://gitlab.cern.ch/dsb/devops/myrepo",
            "dsb/devops/myrepo",
        ),
        (
            "ssh://git@gitlab.cern.ch:7999/ns/subnns/deep/repo.git",
            "ns/subnns/deep/repo",
        ),
    ],
)
def test_project_path_from_remote_parses_url(remote_url: str, expected: str) -> None:
    with patch("dsb_devtools.renovate._renovate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=remote_url + "\n", returncode=0)
        result = _project_path_from_remote()
    assert result == expected


def test_project_path_from_remote_unrecognised_url() -> None:
    with patch("dsb_devtools.renovate._renovate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="https://github.com/some/repo.git\n", returncode=0
        )
        assert _project_path_from_remote() is None


def test_project_path_from_remote_no_git() -> None:
    with patch("dsb_devtools.renovate._renovate.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        assert _project_path_from_remote() is None


# --- _api ---


def _make_response(payload: dict | list, status: int = 200) -> MagicMock:
    body = json.dumps(payload).encode()
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body
    mock_resp.status = status
    return mock_resp


def test_api_get_success() -> None:
    payload = {"id": 42, "name": "myrepo"}
    with patch("dsb_devtools.renovate._renovate.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _make_response(payload)
        result = _api("mytoken", "GET", "/projects/42")
    assert result == payload


def test_api_raises_on_http_error() -> None:
    err = urllib.error.HTTPError(
        url="http://x",
        code=401,
        msg="Unauthorized",
        hdrs=MagicMock(),
        fp=BytesIO(b"Unauthorized"),
    )
    with patch("dsb_devtools.renovate._renovate.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = err
        with pytest.raises(RuntimeError, match="401"):
            _api("badtoken", "GET", "/projects/42")


# --- _get_project_id ---


def test_get_project_id() -> None:
    with patch("dsb_devtools.renovate._renovate._api") as mock_api:
        mock_api.return_value = {"id": 99, "path_with_namespace": "dsb/devops/repo"}
        pid = _get_project_id("tok", "dsb/devops/repo")
    assert pid == 99
    mock_api.assert_called_once_with("tok", "GET", "/projects/dsb%2Fdevops%2Frepo")


# --- _set_ci_variable ---


def test_set_ci_variable_creates_when_absent() -> None:
    with patch("dsb_devtools.renovate._renovate._api") as mock_api:
        mock_api.side_effect = [
            [],  # GET variables — empty
            {"key": "RENOVATE_TOKEN"},  # POST response
        ]
        _set_ci_variable("tok", 42, "RENOVATE_TOKEN", "secret")

    calls = mock_api.call_args_list
    assert calls[0][0][1] == "GET"
    assert calls[1][0][1] == "POST"
    assert calls[1][0][3]["key"] == "RENOVATE_TOKEN"
    assert calls[1][0][3]["masked"] is True


def test_set_ci_variable_updates_when_present() -> None:
    with patch("dsb_devtools.renovate._renovate._api") as mock_api:
        mock_api.side_effect = [
            [{"key": "RENOVATE_TOKEN", "value": "old"}],  # GET variables
            {"key": "RENOVATE_TOKEN"},  # PUT response
        ]
        _set_ci_variable("tok", 42, "RENOVATE_TOKEN", "newsecret")

    calls = mock_api.call_args_list
    assert calls[1][0][1] == "PUT"
    assert calls[1][0][3]["value"] == "newsecret"


# --- Renovate CI job setup ---


def test_write_renovate_ci_template_creates_file(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".gitlab").mkdir(parents=True)
    with patch("dsb_devtools.renovate._renovate._template_dir") as mock_template_dir:
        mock_template_dir.return_value = tmp_path
        source = tmp_path / ".gitlab" / "renovate.gitlab-ci.yml"
        source.write_text("renovate:\n  script:\n    - renovate\n")

        dest = tmp_path / "repo"
        dest.mkdir()
        _write_renovate_ci_template(dest)

    target = dest / ".gitlab" / "renovate.gitlab-ci.yml"
    assert target.exists()
    assert target.read_text() == source.read_text()


def test_ensure_renovate_ci_include_adds_include(tmp_path: pathlib.Path) -> None:
    ci_path = tmp_path / ".gitlab-ci.yml"
    ci_path.write_text(
        """
include:
  - project: acc-co/devops/python/acc-py-gitlab-ci-templates
    file: v2/python.gitlab-ci.yml
""".strip()
        + "\n"
    )

    _ensure_renovate_ci_include(tmp_path)

    content = ci_path.read_text()
    assert "local: .gitlab/renovate.gitlab-ci.yml" in content


def test_ensure_renovate_ci_include_no_duplicate(tmp_path: pathlib.Path) -> None:
    ci_path = tmp_path / ".gitlab-ci.yml"
    ci_path.write_text(
        """
include:
  - local: .gitlab/renovate.gitlab-ci.yml
""".strip()
        + "\n"
    )

    _ensure_renovate_ci_include(tmp_path)

    content = ci_path.read_text()
    assert content.count(".gitlab/renovate.gitlab-ci.yml") == 1


def test_ensure_renovate_ci_job_entry_adds_job(tmp_path: pathlib.Path) -> None:
    ci_path = tmp_path / ".gitlab-ci.yml"
    ci_path.write_text("variables:\n  project_name: demo\n")

    _ensure_renovate_ci_job_entry(tmp_path)

    content = ci_path.read_text()
    assert "\nrenovate:" in content
    assert "extends: .renovate" in content


def test_ensure_renovate_ci_job_entry_no_duplicate(tmp_path: pathlib.Path) -> None:
    ci_path = tmp_path / ".gitlab-ci.yml"
    ci_path.write_text("variables:\n  foo: bar\n\nrenovate:\n  extends: .renovate\n")

    _ensure_renovate_ci_job_entry(tmp_path)

    assert ci_path.read_text().count("renovate:") == 1


def test_ensure_renovate_ci_job_entry_missing_ci(tmp_path: pathlib.Path) -> None:
    _ensure_renovate_ci_job_entry(tmp_path)  # should not raise


def test_ensure_renovate_ci_job_writes_template_and_include(
    tmp_path: pathlib.Path,
) -> None:
    ci_path = tmp_path / ".gitlab-ci.yml"
    ci_path.write_text("variables:\n  project_name: demo\n")

    template_root = tmp_path / "templates"
    (template_root / ".gitlab").mkdir(parents=True)
    (template_root / ".gitlab" / "renovate.gitlab-ci.yml").write_text(
        "renovate:\n  script:\n    - renovate\n"
    )

    with patch("dsb_devtools.renovate._renovate._template_dir") as mock_template_dir:
        mock_template_dir.return_value = template_root
        ensure_renovate_ci_job(tmp_path)

    content = ci_path.read_text()
    assert (tmp_path / ".gitlab" / "renovate.gitlab-ci.yml").exists()
    assert "local: .gitlab/renovate.gitlab-ci.yml" in content
    assert "renovate:" in content
    assert "extends: .renovate" in content


# --- CLI parser ---


def test_parser_setup_command() -> None:
    parser = make_parser()
    args = parser.parse_args(["--project", "dsb/repo", "--token", "tok", "setup"])
    assert args.command == "setup"
    assert args.project_path == "dsb/repo"
    assert args.token == "tok"


def test_parser_teardown_command() -> None:
    parser = make_parser()
    args = parser.parse_args(["teardown"])
    assert args.command == "teardown"
    assert args.project_path is None
    assert args.token is None


def test_parser_update_command() -> None:
    parser = make_parser()
    args = parser.parse_args(["update"])
    assert args.command == "update"


def test_parser_requires_subcommand() -> None:
    parser = make_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
