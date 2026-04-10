from __future__ import annotations

import json
import subprocess
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from dsb_devtools.renovate._renovate import (
    _api,
    _get_project_id,
    _project_path_from_remote,
    _set_ci_variable,
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
