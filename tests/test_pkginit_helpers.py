from __future__ import annotations

import pathlib

import pytest
import ruamel.yaml
import tomlkit

from dsb_devtools.pkginit._input import TemplateConfig
from dsb_devtools.pkginit._pkginit import (
    _edit_gitignore,
    _edit_gitlab_ci,
    _edit_pyproject,
    _make_readme,
)


@pytest.fixture
def mock_config() -> TemplateConfig:
    return TemplateConfig(
        author_name="Test Author",
        author_email="test@example.com",
        package_name="test-package",
        package_module="test_package",
        package_url="https://gitlab.cern.ch/test/test-package.git",
        package_description="A test package description",
        package_dir=pathlib.Path("/tmp/nowhere"),
        use_ci=True,
        use_precommit=True,
        use_docs=True,
        use_tests=True,
        use_java=False,
    )


def test_make_readme(tmp_path: pathlib.Path, mock_config: TemplateConfig) -> None:
    readme_path = tmp_path / "README.md"
    _make_readme(readme_path, mock_config)

    assert readme_path.exists()
    content = readme_path.read_text()
    assert "# test-package" in content
    assert "A test package description" in content
    assert "Documentation available on [Acc-Py docserver]" in content
    assert "https://acc-py.web.cern.ch/gitlab/test/test-package/docs/stable" in content


def test_make_readme_bare(tmp_path: pathlib.Path, mock_config: TemplateConfig) -> None:
    mock_config.package_url = "bare"
    readme_path = tmp_path / "README.md"
    _make_readme(readme_path, mock_config)

    content = readme_path.read_text()
    assert "Documentation available on" not in content


def test_edit_gitignore(tmp_path: pathlib.Path) -> None:
    gitignore_path = tmp_path / ".gitignore"
    # Create dummy gitignore with placeholder
    gitignore_path.write_text("package_name/_version.py\n")

    _edit_gitignore(gitignore_path, "my_cool_package")

    content = gitignore_path.read_text()
    assert "my_cool_package/_version.py" in content
    assert "package_name" not in content


def test_edit_pyproject(tmp_path: pathlib.Path, mock_config: TemplateConfig) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    # Create dummy pyproject.toml
    initial_toml = """
[project]
name = "package_name"
description = "package_description"
authors = [{name = "author_name", email = "author_email"}]

[project.urls]
homepage = "homepage_url"
repository = "repository_url"
changelog = "changelog_url"
documentation = "documentation_url"

[tool.setuptools_scm]
write_to = "package_name/_version.py"

[tool.setuptools.packages.find]
include = ["package_name*"]

[tool.setuptools.package-data]
package_name = ["py.typed"]
"""
    pyproject_path.write_text(initial_toml)

    _edit_pyproject(pyproject_path, mock_config)

    content = pyproject_path.read_text()
    data = tomlkit.parse(content)

    assert data["project"]["name"] == "test-package"
    assert data["project"]["description"] == "A test package description"
    assert data["project"]["authors"][0]["name"] == "Test Author"
    assert data["project"]["authors"][0]["email"] == "test@example.com"

    urls = data["project"]["urls"]
    assert urls["homepage"] == "https://gitlab.cern.ch/test/test-package"
    assert urls["repository"] == "https://gitlab.cern.ch/test/test-package"

    assert data["tool"]["setuptools_scm"]["write_to"] == "test_package/_version.py"
    assert data["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "test_package*"
    ]

    # Check package data key update
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "test_package" in package_data
    assert "package_name" not in package_data


def test_edit_gitlab_ci_full(
    tmp_path: pathlib.Path, mock_config: TemplateConfig
) -> None:
    ci_path = tmp_path / ".gitlab-ci.yml"
    initial_yaml = """
variables:
  project_name: package_name
  ACC_PY_BASE_IMAGE_NAME: acc-py_cc7_ci

._build_docs: &build_docs
  script: echo docs

build_docs:
  <<: *build_docs

build_docs_on_tag:
  <<: *build_docs

pre-commit:
  script: echo pre-commit

test_dev:
  script: echo test

test_wheel:
  script: echo wheel
"""
    ci_path.write_text(initial_yaml)

    _edit_gitlab_ci(ci_path, mock_config)

    yaml = ruamel.yaml.YAML()
    data = yaml.load(ci_path.read_text())

    assert data["variables"]["project_name"] == "test-package"
    # Docs enabled
    assert "build_docs" in data
    assert "build_docs_on_tag" in data
    # Pre-commit enabled
    assert "pre-commit" in data
    # Tests enabled
    assert "test_dev" in data

    # Java not enabled, so image should NOT change
    assert data["variables"]["ACC_PY_BASE_IMAGE_NAME"] == "acc-py_cc7_ci"


def test_edit_gitlab_ci_minimal(
    tmp_path: pathlib.Path, mock_config: TemplateConfig
) -> None:
    mock_config.use_docs = False
    mock_config.use_precommit = False
    mock_config.use_tests = False
    mock_config.use_java = True  # Enable Java to test image change

    ci_path = tmp_path / ".gitlab-ci.yml"
    initial_yaml = """
variables:
  project_name: package_name
  ACC_PY_BASE_IMAGE_NAME: acc-py_cc7_ci

._build_docs: &build_docs
  script: echo docs

build_docs:
  <<: *build_docs

build_docs_on_tag:
  <<: *build_docs

pre-commit:
  script: echo pre-commit

test_dev:
  script: echo test

test_wheel:
  script: echo wheel
"""
    ci_path.write_text(initial_yaml)

    _edit_gitlab_ci(ci_path, mock_config)

    yaml = ruamel.yaml.YAML()
    data = yaml.load(ci_path.read_text())

    assert "build_docs" not in data
    assert "pre-commit" not in data
    assert "test_dev" not in data

    # Java enabled, check image
    assert data["variables"]["ACC_PY_BASE_IMAGE_NAME"] == "acc-py_cc7_openjdk11_ci"


def test_edit_gitlab_ci_java_extends(
    tmp_path: pathlib.Path, mock_config: TemplateConfig
) -> None:
    # Test adding java extends to test_dev
    mock_config.use_tests = True
    mock_config.use_java = True

    ci_path = tmp_path / ".gitlab-ci.yml"
    initial_yaml = """
variables:
  project_name: package_name

test_dev:
  extends: .existing_template
  script: echo test
"""
    ci_path.write_text(initial_yaml)

    _edit_gitlab_ci(ci_path, mock_config)

    yaml = ruamel.yaml.YAML()
    data = yaml.load(ci_path.read_text())

    assert ".acc_py_run_on_acc_py" in data["test_dev"]["extends"]
    assert ".existing_template" in data["test_dev"]["extends"]
