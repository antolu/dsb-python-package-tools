from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import traceback
import typing

import rich
import rich.console
import ruamel.yaml
import survey.routines
import tomlkit

from ._input import (
    TemplateConfig,
    ask_specific_input,
    assert_input_valid,
    confirm_input,
    create_config,
    parse_args,
    read_input,
    resolve_changelog_url,
    resolve_docs_url,
    resolve_git_url,
    set_config_defaults,
)

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"


BANNER = r"""


██████  ███████ ██████      ██████  ██   ██  ██████  ██ ███    ██ ██ ████████
██   ██ ██      ██   ██     ██   ██ ██  ██  ██       ██ ████   ██ ██    ██
██   ██ ███████ ██████      ██████  █████   ██   ███ ██ ██ ██  ██ ██    ██
██   ██      ██ ██   ██     ██      ██  ██  ██    ██ ██ ██  ██ ██ ██    ██
██████  ███████ ██████      ██      ██   ██  ██████  ██ ██   ████ ██    ██


"""


def print_success(msg: str) -> None:
    rich.print(f"[bold green]✓[/bold green] {msg}")


def print_in_progress(msg: str) -> None:
    rich.print(f"[bold blue].[/bold blue] {msg}")


def print_failure(msg: str) -> None:
    rich.print(f"[bold red]✗[/bold red] {msg}")


def print_banner() -> None:
    print(BANNER)


def _set_config_defaults(config: TemplateConfig) -> None:
    """Set default values for None fields."""
    set_config_defaults(config)


def main(
    argv: list[str] | argparse.Namespace | None = None,
    parser: argparse.ArgumentParser | None = None,
) -> None:
    # make welcome screen, CTRL+C to exit
    if isinstance(argv, argparse.Namespace):
        config = create_config(argv)
    else:
        argv = argv or sys.argv[1:]

        config = parse_args(argv, parser)

    os.system("clear")
    print_banner()

    if not config.no_confirm:
        try:
            config = read_input(config)

            if not confirm_input(config):
                config = ask_specific_input(config)
        except KeyboardInterrupt:
            print_success("\nRead CTRL+C")
            sys.exit(0)
    else:
        try:
            assert_input_valid(config)
        except AssertionError as e:
            print_failure(str(e))
            sys.exit(1)

        _set_config_defaults(config)

    print()
    try:
        pkginit(config)
    except Exception as e:
        print_failure(f"Failed to initialize package: {e}\n{traceback.format_exc()}")
        sys.exit(1)


def _validate_dest_dir(dest_dir: pathlib.Path) -> None:
    """Validate that destination directory is safe to use."""
    if dest_dir.exists():
        if not dest_dir.is_dir():
            msg = f"{dest_dir} exists and is not a directory"
            raise ValueError(msg)

        # Check if directory is not empty
        if any(dest_dir.iterdir()):
            rich.print(
                f"[yellow]Warning:[/yellow] {dest_dir} already exists and is not empty"
            )
            if not survey.routines.inquire(
                f"Delete all contents of {dest_dir}? ", default=False
            ):
                msg = "Operation cancelled by user"
                raise RuntimeError(msg)


def pkginit(config: TemplateConfig) -> None:
    """
    Make a temporary directory and copy the template files to it.

    Then make the necessary edits to the files, and copy the whole directory
    to config.package_dir
    """
    dest_dir = config.package_dir
    _validate_dest_dir(dest_dir)

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = pathlib.Path(tmp_dir_str)

        # Copy the template files to the temporary directory
        files_to_copy = [
            "pyproject.toml",
            ".gitignore",
        ]
        for file_ in files_to_copy:
            shutil.copy(TEMPLATE_DIR / file_, tmp_dir / file_)

        shutil.copytree(TEMPLATE_DIR / "package_name", tmp_dir / "package_name")

        (tmp_dir / "package_name").rename(tmp_dir / config.package_module)
        _edit_gitignore(tmp_dir / ".gitignore", config.package_module)
        _make_readme(tmp_dir / "README.md", config)
        _edit_pyproject(tmp_dir / "pyproject.toml", config)

        if config.use_docs:
            shutil.copytree(TEMPLATE_DIR / "docs", tmp_dir / "docs")
            _edit_docs(
                tmp_dir / "docs",
                config.package_name,
                config.package_module,
                config.author_name,
            )

        if config.use_tests:
            shutil.copytree(TEMPLATE_DIR / "tests", tmp_dir / "tests")

        if config.use_precommit:
            shutil.copy(
                TEMPLATE_DIR / ".pre-commit-config.yaml",
                tmp_dir / ".pre-commit-config.yaml",
            )

        if config.use_ci:
            shutil.copy(
                TEMPLATE_DIR / ".gitlab-ci.yml",
                tmp_dir / ".gitlab-ci.yml",
            )
            _edit_gitlab_ci(tmp_dir / ".gitlab-ci.yml", config)

        # set up git and pre-commit
        if config.package_url != "bare":
            try:
                _setup_vcs(tmp_dir, config.package_url)
            except RuntimeError as e:
                print_failure(
                    "Failed to setup git repository. "
                    "Please run `git init` in the repository directory"
                    "to initialize the repository manually.\n\n"
                    f"Error: {e}"
                )
        else:
            print_success("Skipping git setup as package_url is 'bare'")

        if config.use_precommit:
            try:
                _setup_precommit(tmp_dir)
            except RuntimeError as e:
                print(
                    "Failed to setup pre-commit hooks. "
                    "Please run `pre-commit install` in the repository directory"
                    "to install the hooks manually.\n"
                    f"Error: {e}"
                )

        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(tmp_dir, dest_dir)

    print(
        "Run `pip install -e . --config-settings editable_mode=compat` to get started"
    )


def _edit_gitignore(gitignore_path: pathlib.Path, package_module: str) -> None:
    _replace_in_file(gitignore_path, package_name=package_module)
    print_success(f"Added {package_module}/_version.py to .gitignore")


def _make_readme(
    readme_path: pathlib.Path,
    package_name: str | TemplateConfig,
    package_description: str | None = None,
    docs_url: str | None = None,
) -> None:
    if isinstance(package_name, TemplateConfig):
        package_name_s = package_name.package_name
        package_description = package_name.package_description
        if package_name.package_url != "bare" and package_name.use_docs:
            docs_url = resolve_docs_url(package_name)
    else:
        package_name_s = package_name

    with open(readme_path, "w") as f:
        f.write(f"# {package_name_s}\n\n")
        if package_description:
            f.write(f"{package_description}\n\n")
        f.write("This is a package generated by dsb-devtools\n")
        f.write(
            "To get started, run "
            "`pip install -e . --config-settings editable_mode=compat`"
        )

        if docs_url:
            f.write(f"\n\nDocumentation available on [Acc-Py docserver]({docs_url})")
        f.write("\n")

    if docs_url:
        print_success(
            "README.md is all set with package name, description and docs link"
        )
    else:
        print_success("README.md is all set with package name and description")


def _edit_pyproject(pyproject_path: pathlib.Path, config: TemplateConfig) -> None:
    with open(pyproject_path) as f:
        toml = tomlkit.loads(f.read())

    toml["project"]["name"] = config.package_name  # type: ignore[index]
    toml["project"]["description"] = config.package_description  # type: ignore[index]
    toml["project"]["authors"][0]["name"] = config.author_name  # type: ignore[index]
    toml["project"]["authors"][0]["email"] = config.author_email  # type: ignore[index]

    if config.package_url != "bare":
        toml["project"]["urls"]["homepage"] = resolve_git_url(config)  # type: ignore[index]
        toml["project"]["urls"]["repository"] = resolve_git_url(  # type: ignore[index]
            config
        )
        toml["project"]["urls"]["changelog"] = resolve_changelog_url(config)  # type: ignore[index]
        toml["project"]["urls"]["documentation"] = resolve_docs_url(  # type: ignore[index]
            config
        )

    toml["tool"]["setuptools_scm"]["write_to"] = f"{config.package_module}/_version.py"  # type: ignore[index]

    toml["tool"]["setuptools"]["packages"]["find"]["include"] = [  # type: ignore[index]
        f"{config.package_module}*",
    ]
    del toml["tool"]["setuptools"]["package-data"]["package_name"]  # type: ignore[index,union-attr]
    toml["tool"]["setuptools"]["package-data"][config.package_module] = [  # type: ignore[index]
        "py.typed",
    ]

    with open(pyproject_path, "w") as f:
        f.write(tomlkit.dumps(toml))

    print_success("pyproject.toml is all good!")


def _replace_in_file(
    file_path: pathlib.Path,
    replace: dict[str, str] | None = None,
    **kwargs: typing.Any,
) -> None:
    replace = replace or {}
    replace.update(kwargs)
    with open(file_path) as f:
        lines = f.readlines()

    for i, line in enumerate(list(lines)):
        for old, new in replace.items():
            if old in line:
                lines[i] = line.replace(old, new)

    with open(file_path, "w") as f:
        f.writelines(lines)


def _edit_docs(
    docs_root: pathlib.Path,
    package_name: str,
    package_module: str,
    author_name: str,
) -> None:
    docs_root = docs_root / "source"
    _replace_in_file(
        docs_root / "conf.py",
        {
            "package_name": package_module,
            "package-name": package_name,
            "author = Anton Lu": f'author = "{author_name}"',
        },
    )
    _replace_in_file(
        docs_root / "api.rst",
        {"package_name": package_module, "package-name": package_name},
    )
    _replace_in_file(
        docs_root / "index.rst",
        {"package-name": package_name},
    )

    msg = "Injected package name into "
    msg += "docs/source/{conf.py,api.rst,index.rst}."
    print_success(msg)


def _edit_gitlab_ci(
    gitlab_ci_conf_path: pathlib.Path,
    config: TemplateConfig,
) -> None:
    yaml = ruamel.yaml.YAML(typ="rt")
    with open(gitlab_ci_conf_path) as f:
        ci_conf = yaml.load(f)

    ci_conf["variables"]["project_name"] = config.package_name

    if not config.use_docs:
        ci_conf.pop("._build_docs")
        ci_conf.pop("build_docs")
        ci_conf.pop("build_docs_on_tag")

    if not config.use_precommit:
        ci_conf.pop("pre-commit")

    if not config.use_tests:
        ci_conf.pop("test_dev")
        ci_conf.pop("test_wheel")

    if config.use_java:
        ci_conf["variables"]["ACC_PY_BASE_IMAGE_NAME"] = "acc-py_cc7_openjdk11_ci"

        if config.use_tests:
            if "extends" in ci_conf["test_dev"]:
                if isinstance(ci_conf["test_dev"]["extends"], str):
                    ci_conf["test_dev"]["extends"] = [ci_conf["test_dev"]["extends"]]
                ci_conf["test_dev"]["extends"].append(".acc_py_run_on_acc_py")
            else:
                ci_conf["test_dev"]["extends"] = [".acc_py_run_on_acc_py"]

    with open(gitlab_ci_conf_path, "w") as f:
        yaml.dump(ci_conf, f)

    msg = "CI pipeline set up with: "
    if config.use_docs:
        msg += "docs build & release, "
    if config.use_precommit:
        msg += "pre-commit hooks, "
    if config.use_tests:
        msg += "dev and wheel tests, "
    if config.use_java:
        msg += "acc-py_cc7_openjdk11_ci base image, "
    msg = msg[:-2] + "."
    print_success(msg)


def _setup_vcs(repo_dir: pathlib.Path, repo_url: str) -> None:
    cwd = pathlib.Path.cwd()

    try:
        os.chdir(repo_dir)

        command = ["git", "init"]
        run_command(command, repo_dir, "Failed to initialize git repository:\n")
        print_success("Initialized git repository in the package directory")

        command = ["git", "remote", "add", "origin", repo_url]
        run_command(command, repo_dir, "Failed to add remote origin\n")
        print_success(f"Pointed origin to {repo_url}")

        # checkout master branch and set it as default
        command = ["git", "branch", "-M", "master"]
        run_command(
            command,
            repo_dir,
            "Failed to set master branch as default branch:\n",
        )
        print_success("Set default branch to master")

        # add all files to staging area
        command = ["git", "add", "."]
        run_command(
            command,
            repo_dir,
            "Failed to add all files to staging area:\n",
        )
        print_success("Added all files to staging area")

        # commit all files
        command = ["git", "commit", "-m", "Initial commit"]
        run_command(
            command,
            repo_dir,
            "Failed to commit all files:\n",
        )
        print_success("Committed all files as initial commit")

        # push to remote (the -u flag sets up tracking automatically)
        command = ["git", "push", "-u", "origin", "master"]
        run_command(
            command,
            repo_dir,
            "Failed to push to remote master branch:\n",
        )
        print_success("Pushed to remote master branch")
    finally:
        os.chdir(cwd)


def run_command(command: list[str], cwd: pathlib.Path, error_msg: str | None) -> None:
    try:
        output = subprocess.run(
            command,
            check=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if output.returncode != 0:
            raise RuntimeError(
                (error_msg or "Failed to run command: \n") + output.stdout.decode()
            )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            (error_msg or "Failed to run command: \n") + e.stdout.decode()
        ) from e


def _setup_precommit(repo_dir: pathlib.Path) -> None:
    cwd = pathlib.Path().cwd()

    try:
        os.chdir(repo_dir)

        # check if pre-commit is installed
        if shutil.which("pre-commit") is None:
            print_in_progress("pre-commit not found, installing...")
            command = [sys.executable, "-m", "pip", "install", "pre-commit"]
            run_command(command, repo_dir, "Failed to install pre-commit:\n")

        command = ["pre-commit", "install"]
        run_command(command, repo_dir, "Failed to install pre-commit hooks:\n")
        print_success(
            "Installed pre-commit hooks. Use `pre-commit run` to test run them."
        )
    finally:
        os.chdir(cwd)
