from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch

import pytest

from dsb_devtools.pkginit._input import TemplateConfig
from dsb_devtools.pkginit._pkginit import _validate_dest_dir, pkginit


@pytest.fixture
def mock_config(tmp_path: pathlib.Path) -> TemplateConfig:
    return TemplateConfig(
        author_name="Test Author",
        author_email="test@example.com",
        package_name="test-package",
        package_module="test_package",
        package_url="https://gitlab.cern.ch/test/test-package.git",
        package_description="A test package description",
        package_dir=tmp_path / "test-package",
        use_ci=True,
        use_precommit=True,
        use_docs=True,
        use_tests=True,
        use_java=False,
    )


@patch("dsb_devtools.pkginit._pkginit._setup_precommit")
@patch("dsb_devtools.pkginit._pkginit._setup_vcs")
def test_pkginit_structure(
    mock_setup_vcs: MagicMock,
    mock_setup_precommit: MagicMock,
    mock_config: TemplateConfig,
) -> None:
    """Test that pkginit creates the correct directory structure."""
    pkginit(mock_config)

    package_dir = mock_config.package_dir
    assert package_dir.exists()
    assert package_dir.is_dir()

    # Check structure
    assert (package_dir / "test_package").is_dir()
    assert (package_dir / "test_package" / "__init__.py").exists()

    assert (package_dir / "docs").is_dir()
    assert (package_dir / "tests").is_dir()

    assert (package_dir / "pyproject.toml").exists()
    assert (package_dir / "README.md").exists()
    assert (package_dir / ".gitignore").exists()
    assert (package_dir / ".gitlab-ci.yml").exists()

    # Verify mocks called
    mock_setup_vcs.assert_called_once()
    mock_setup_precommit.assert_called_once()


@patch("dsb_devtools.pkginit._pkginit._setup_precommit")
@patch("dsb_devtools.pkginit._pkginit._setup_vcs")
@patch("survey.routines.inquire")
def test_pkginit_clears_directory(
    mock_inquire: MagicMock,
    mock_setup_vcs: MagicMock,
    mock_setup_precommit: MagicMock,
    mock_config: TemplateConfig,
) -> None:
    """Test that pkginit clears existing directory contents (validation moved to main)."""
    package_dir = mock_config.package_dir
    package_dir.mkdir()

    # Create a file that should be deleted
    (package_dir / "old_file.txt").write_text("should be gone")

    # pkginit should NOT prompt anymore, it assumes validation passed
    pkginit(mock_config)

    # Old file should be gone
    assert not (package_dir / "old_file.txt").exists()

    # New files should be present
    assert (package_dir / "pyproject.toml").exists()
    assert (package_dir / "test_package").is_dir()

    # Should NOT have prompted
    mock_inquire.assert_not_called()


@patch("survey.routines.inquire")
def test_validate_dest_dir_prompts_on_overwrite(
    mock_inquire: MagicMock,
    mock_config: TemplateConfig,
) -> None:
    """Test that _validate_dest_dir prompts when directory is not empty."""
    package_dir = mock_config.package_dir
    package_dir.mkdir()
    (package_dir / "existing.txt").write_text("old")

    # Simulate user confirmation
    mock_inquire.return_value = True

    _validate_dest_dir(package_dir)

    mock_inquire.assert_called_once()
    assert "Delete all contents" in mock_inquire.call_args[0][0]


@patch("survey.routines.inquire")
def test_validate_dest_dir_aborts_if_denied(
    mock_inquire: MagicMock,
    mock_config: TemplateConfig,
) -> None:
    """Test that _validate_dest_dir aborts if user denies overwrite."""
    package_dir = mock_config.package_dir
    package_dir.mkdir()
    (package_dir / "existing.txt").write_text("old")

    # Simulate user denial
    mock_inquire.return_value = False

    with pytest.raises(RuntimeError, match="Operation cancelled by user"):
        _validate_dest_dir(package_dir)


@patch("dsb_devtools.pkginit._pkginit._setup_precommit")
@patch("dsb_devtools.pkginit._pkginit._setup_vcs")
def test_pkginit_minimal_config(
    mock_setup_vcs: MagicMock,
    mock_setup_precommit: MagicMock,
    mock_config: TemplateConfig,
) -> None:
    """Test pkginit with minimal configuration (no docs, tests, ci, precommit)."""
    mock_config.use_ci = False
    mock_config.use_docs = False
    mock_config.use_tests = False
    mock_config.use_precommit = False
    mock_config.package_url = "bare"

    pkginit(mock_config)

    package_dir = mock_config.package_dir

    # Should NOT exist
    assert not (package_dir / "docs").exists()
    assert not (package_dir / "tests").exists()
    assert not (package_dir / ".gitlab-ci.yml").exists()
    assert not (package_dir / ".pre-commit-config.yaml").exists()

    # Should exist
    assert (package_dir / "test_package").is_dir()
    assert (package_dir / "pyproject.toml").exists()

    # Version control should NOT be set up
    mock_setup_vcs.assert_not_called()
    mock_setup_precommit.assert_not_called()
