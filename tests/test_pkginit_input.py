from __future__ import annotations

from unittest.mock import MagicMock, patch

from dsb_devtools.pkginit._input import (
    TemplateConfig,
    _maybe_read_use_ci,
    _maybe_read_use_docs,
    _maybe_read_use_java,
    _maybe_read_use_precommit,
    _maybe_read_use_tests,
    create_config,
    make_parser,
    set_config_defaults,
)


def test_no_args_all_none_before_defaults() -> None:
    """When no CLI args are provided, boolean fields should be None."""
    parser = make_parser()
    args = parser.parse_args([])
    config = create_config(args)

    assert config.use_ci is None
    assert config.use_precommit is None
    assert config.use_docs is None
    assert config.use_tests is None
    assert config.use_java is None


def test_set_config_defaults_applies_when_none() -> None:
    """set_config_defaults should set values only when None."""
    config = TemplateConfig(
        author_name="Test",
        author_email="test@example.com",
        package_name="test-pkg",
        package_module="test_pkg",
        package_url="bare",
        package_description="Test description",
        use_ci=None,
        use_precommit=None,
        use_docs=None,
        use_tests=None,
        use_java=None,
    )
    set_config_defaults(config)

    assert config.use_ci is True
    assert config.use_precommit is True
    assert config.use_docs is True
    assert config.use_tests is True
    assert config.use_java is False


def test_cli_flag_no_ci_overrides_default() -> None:
    """--no-ci flag should set use_ci to False and not be overridden by defaults."""
    parser = make_parser()
    args = parser.parse_args(["--no-ci"])
    config = create_config(args)

    assert config.use_ci is False

    set_config_defaults(config)
    assert config.use_ci is False, (
        "set_config_defaults should not override user-provided False"
    )


def test_cli_flag_ci_sets_true() -> None:
    """--ci flag should set use_ci to True."""
    parser = make_parser()
    args = parser.parse_args(["--ci"])
    config = create_config(args)

    assert config.use_ci is True

    set_config_defaults(config)
    assert config.use_ci is True


def test_cli_flag_no_docs_overrides_default() -> None:
    """--no-docs flag should set use_docs to False."""
    parser = make_parser()
    args = parser.parse_args(["--no-docs"])
    config = create_config(args)

    assert config.use_docs is False

    set_config_defaults(config)
    assert config.use_docs is False


def test_cli_flag_no_tests_overrides_default() -> None:
    """--no-tests flag should set use_tests to False."""
    parser = make_parser()
    args = parser.parse_args(["--no-tests"])
    config = create_config(args)

    assert config.use_tests is False

    set_config_defaults(config)
    assert config.use_tests is False


def test_cli_flag_no_precommit_overrides_default() -> None:
    """--no-precommit flag should set use_precommit to False."""
    parser = make_parser()
    args = parser.parse_args(["--no-precommit"])
    config = create_config(args)

    assert config.use_precommit is False

    set_config_defaults(config)
    assert config.use_precommit is False


def test_multiple_negative_flags() -> None:
    """Multiple --no-* flags should all be respected."""
    parser = make_parser()
    args = parser.parse_args(["--no-ci", "--no-docs", "--no-tests"])
    config = create_config(args)

    assert config.use_ci is False
    assert config.use_docs is False
    assert config.use_tests is False
    assert config.use_precommit is None  # Not specified, should be None

    set_config_defaults(config)
    assert config.use_ci is False
    assert config.use_docs is False
    assert config.use_tests is False
    assert config.use_precommit is True  # Default should be applied


def test_mixed_positive_negative_flags() -> None:
    """Mix of positive and negative flags should be respected."""
    parser = make_parser()
    args = parser.parse_args(["--ci", "--no-docs"])
    config = create_config(args)

    assert config.use_ci is True
    assert config.use_docs is False

    set_config_defaults(config)
    assert config.use_ci is True
    assert config.use_docs is False


def test_java_ci_flag() -> None:
    """--java-ci flag should set use_java to True."""
    parser = make_parser()
    args = parser.parse_args(["--java-ci"])
    config = create_config(args)

    assert config.use_java is True

    set_config_defaults(config)
    assert config.use_java is True


def test_java_default_when_not_specified() -> None:
    """use_java should default to False when not specified."""
    parser = make_parser()
    args = parser.parse_args([])
    config = create_config(args)

    assert config.use_java is None

    set_config_defaults(config)
    assert config.use_java is False


def test_all_positive_flags() -> None:
    """All positive flags should set their values to True."""
    parser = make_parser()
    args = parser.parse_args(["--ci", "--precommit", "--docs", "--tests", "--java-ci"])
    config = create_config(args)

    assert config.use_ci is True
    assert config.use_precommit is True
    assert config.use_docs is True
    assert config.use_tests is True
    assert config.use_java is True

    set_config_defaults(config)
    # All should remain True
    assert config.use_ci is True
    assert config.use_precommit is True
    assert config.use_docs is True
    assert config.use_tests is True
    assert config.use_java is True


# Interactive behavior tests


@patch("dsb_devtools.pkginit._input.routines.inquire")
def test_maybe_read_use_ci_skips_when_none(mock_inquire: MagicMock) -> None:
    """It should NOT ask for input when use_ci is None (defaults are applied later)."""
    config = TemplateConfig(
        author_name="Me",
        author_email="me@cern.ch",
        package_name="test-package",
        package_module="test_package",
        package_url="https://gitlab.cern.ch/namespace/test-package.git",
        package_description="Description",
        use_ci=None,
    )

    _maybe_read_use_ci(config, force=False)

    mock_inquire.assert_not_called()
    assert config.use_ci is None


@patch("dsb_devtools.pkginit._input.routines.inquire")
def test_maybe_read_use_ci_skips_when_already_set(mock_inquire: MagicMock) -> None:
    """_maybe_read_use_ci should NOT prompt when value is already set."""
    config = TemplateConfig(
        author_name="Test",
        author_email="test@example.com",
        package_name="test-pkg",
        package_module="test_pkg",
        package_url="bare",
        package_description="Test description",
        use_ci=False,
    )

    _maybe_read_use_ci(config, force=False)

    # Should NOT have prompted
    mock_inquire.assert_not_called()
    assert config.use_ci is False


@patch("dsb_devtools.pkginit._input.routines.inquire")
def test_maybe_read_use_ci_prompts_when_force(mock_inquire: MagicMock) -> None:
    """_maybe_read_use_ci should always prompt when force=True."""
    mock_inquire.return_value = True

    config = TemplateConfig(
        author_name="Test",
        author_email="test@example.com",
        package_name="test-pkg",
        package_module="test_pkg",
        package_url="bare",
        package_description="Test description",
        use_ci=False,  # Already set to False
    )

    _maybe_read_use_ci(config, force=True)

    # Should have prompted even though already set
    mock_inquire.assert_called_once()
    assert config.use_ci is True


@patch("dsb_devtools.pkginit._input.routines.inquire")
def test_maybe_read_use_docs_skips_when_none(mock_inquire: MagicMock) -> None:
    """_maybe_read_use_docs should NOT prompt when value is None (defaults later)."""
    config1 = TemplateConfig(
        author_name="Test",
        author_email="test@example.com",
        package_name="test-pkg",
        package_module="test_pkg",
        package_url="bare",
        package_description="Test description",
        use_docs=None,
    )
    _maybe_read_use_docs(config1, force=False)
    mock_inquire.assert_not_called()
    assert config1.use_docs is None  # should NOT prompt
    mock_inquire.reset_mock()
    config2 = TemplateConfig(
        author_name="Test",
        author_email="test@example.com",
        package_name="test-pkg",
        package_module="test_pkg",
        package_url="bare",
        package_description="Test description",
        use_docs=False,
    )
    _maybe_read_use_docs(config2, force=False)
    assert mock_inquire.call_count == 0


@patch("dsb_devtools.pkginit._input.routines.inquire")
def test_all_maybe_read_functions_respect_false_values(mock_inquire: MagicMock) -> None:
    """All _maybe_read_use_* functions should respect False values from CLI."""
    config = TemplateConfig(
        author_name="Test",
        author_email="test@example.com",
        package_name="test-pkg",
        package_module="test_pkg",
        package_url="bare",
        package_description="Test description",
        use_ci=False,
        use_docs=False,
        use_tests=False,
        use_precommit=False,
        use_java=False,
    )

    # Call all the _maybe_read functions
    _maybe_read_use_ci(config, force=False)
    _maybe_read_use_docs(config, force=False)
    _maybe_read_use_tests(config, force=False)
    _maybe_read_use_precommit(config, force=False)
    _maybe_read_use_java(config, force=False)

    # None of them should have prompted
    mock_inquire.assert_not_called()

    # Values should remain False
    assert config.use_ci is False
    assert config.use_docs is False
    assert config.use_tests is False
    assert config.use_precommit is False
    assert config.use_java is False
