from __future__ import annotations

import argparse
import configparser
import dataclasses
import io
import os
import pathlib
import re
import typing

import rich.console
import rich.table
from survey import routines, widgets

_EMAIL_REGEX = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
_REPO_REGEX = re.compile(
    r"^(?P<protocol>ssh://(git@)?|https://)gitlab.cern.ch(:\d+)?/"
    r"(?P<namespace>(([\w\-_]+/)*([\w\-_]+)))/"
    r"(?P<reponame>[\w\-_]+)(.git)$"
)
_GITLAB_HTTPS_STEM = "https://gitlab.cern.ch/{namespace}/{reponame}"
_ACC_PY_DOCS_STEM = (
    "https://acc-py.web.cern.ch/gitlab/{namespace}/{reponame}/docs/stable"
)


@dataclasses.dataclass
class TemplateConfig:
    author_name: str
    """ The name of the author. """
    author_email: str
    """ The email of the author. """

    package_name: str
    """ The name of the package. Can contain dashes. """
    package_module: str
    """ The name of the package module. Should be a valid Python module name. Normally, it is the same as the package name. """
    package_url: str
    """ The URL of the package. """

    package_description: str
    """ Short description of the package. """
    package_dir: pathlib.Path = pathlib.Path(".")
    """ The directory where the package will be initialized (the parent directory). """

    use_ci: bool = True
    """ Include a CI configuration. """
    use_precommit: bool = True
    """ Include a pre-commit configuration. """
    use_docs: bool = True
    """ Include documentation. """
    use_tests: bool = True
    """ Include tests. """
    use_java: bool = False
    """ Use CI image that supports Java. """

    no_confirm: bool = False

    def __str__(self) -> str:
        writer = io.StringIO()

        table = rich.table.Table(title="Package init configuration", show_header=False)

        table.add_column("Name", style="bold")
        table.add_column("Value")

        table.add_row("Author name", self.author_name)
        table.add_row("Author email", self.author_email)
        table.add_row("Package description", self.package_description)
        table.add_row("Package name", self.package_name)
        table.add_row("Package module", self.package_module)
        table.add_row("Package directory", str(self.package_dir))
        table.add_row("Package URL", self.package_url)
        table.add_row("Include docs", "Yes" if self.use_docs else "No")
        table.add_row("Include tests", "Yes" if self.use_tests else "No")
        table.add_row("Include pre-commit", "Yes" if self.use_precommit else "No")
        table.add_row("Include CI", "Yes" if self.use_ci else "No")
        if self.use_ci:
            table.add_row("Use Java CI", "Yes" if self.use_java else "No")

        console = rich.console.Console(file=writer)
        console.print(table)

        return writer.getvalue()


def make_parser(
    main_parser: argparse.ArgumentParser | None = None,
) -> argparse.ArgumentParser:
    parser = main_parser or argparse.ArgumentParser(
        description="Initialize a Python package with a template."
    )

    parser.add_argument(
        "--package-name",
        dest="package_name",
        type=str,
        default="",
        help="The name of the package to initialize.",
    )
    parser.add_argument(
        "--package-module",
        dest="package_module",
        type=str,
        default="",
        help="The name of the package module. Should be a valid Python module name."
        "Normally, it is the same as the package name.",
    )
    parser.add_argument(
        "--author",
        type=str,
        default="",
        help="The author of the package.",
    )
    parser.add_argument(
        "--email",
        type=str,
        default="",
        help="The email of the author.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="bare",
        help='The GitLab URL of the package. Use "bare" to not use git.',
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="The description of the package.",
    )
    parser.add_argument(
        "--package-dir",
        type=pathlib.Path,
        default=pathlib.Path("."),
        help="The directory where the package will be initialized.",
    )
    parser.add_argument(
        "--no-ci",
        action="store_false",
        dest="use_ci",
        help="Do not include a CI configuration.",
    )
    parser.add_argument(
        "--no-precommit",
        action="store_false",
        dest="use_precommit",
        help="Do not include a pre-commit configuration.",
    )
    parser.add_argument(
        "--no-docs",
        action="store_false",
        dest="use_docs",
        help="Do not include documentation.",
    )
    parser.add_argument(
        "--no-tests",
        action="store_false",
        dest="use_tests",
        help="Do not include tests.",
    )
    parser.add_argument(
        "--java-ci",
        action="store_true",
        dest="use_java",
        help="Use a CI image that supports Java.",
    )
    parser.add_argument(
        "--no-confirm",
        dest="no_confirm",
        action="store_true",
        help="Do not ask for confirmation.",
    )

    return parser


def parse_args(
    argv: list[str], parser: argparse.ArgumentParser | None = None
) -> TemplateConfig:
    parser = make_parser(main_parser=parser)
    args = parser.parse_args(argv)

    return create_config(args)


def create_config(args: argparse.Namespace) -> TemplateConfig:
    return TemplateConfig(
        author_name=args.author,
        author_email=args.email,
        package_name=args.package_name,
        package_module=args.package_module,
        package_url=args.url,
        package_description=args.description,
        package_dir=args.package_dir,
        use_ci=args.use_ci,
        use_precommit=args.use_precommit,
        use_docs=args.use_docs,
        use_tests=args.use_tests,
        use_java=args.use_java,
        no_confirm=args.no_confirm,
    )


def read_input(config: TemplateConfig, *, force: bool = False) -> TemplateConfig:
    """
    Read the input from the user and update the configuration for missing values.

    Parameters
    ----------
    config : TemplateConfig
        The configuration to update.
    force : bool, optional
        Read the input even if the configuration is complete, by default False.

    Returns
    -------
    TemplateConfig
        The updated configuration.
    """
    _, reponame_hint = _maybe_ask_repo_url(config, force=True)

    _maybe_read_git_user_name(config, force=force)
    _maybe_read_git_user_email(config, force=force)

    _maybe_read_package_name(config, reponame_hint=reponame_hint, force=force)
    _maybe_read_package_module(config, force=force)

    _maybe_ask_package_description(config, force=force)

    _maybe_read_package_dir(config, force=force)

    _maybe_read_use_docs(config, force=force)
    _maybe_read_use_tests(config, force=force)
    _maybe_read_use_precommit(config, force=force)
    _maybe_read_use_ci(config, force=force)
    if config.use_ci:
        _maybe_read_use_java(config, force=force)

    return config


def confirm_input(config: TemplateConfig) -> bool:
    """
    Confirm the input from the user.

    Parameters
    ----------
    config : TemplateConfig
        The configuration to confirm.

    Returns
    -------
    bool
        True if the user confirms the input, False otherwise.
    """
    os.system("clear")
    print(config)

    return routines.inquire("Is this configuration correct? ", default=True)


def assert_input_valid(config: TemplateConfig) -> None:
    empty_fields = [
        field
        for field in (
            "author_name",
            "author_email",
            "package_description",
            "package_name",
            "package_module",
            "package_dir",
            "package_url",
        )
        if getattr(config, field) == ""
    ]

    if len(empty_fields) > 0:
        msg = "The following fields/arguments cannot be empty: "
        msg += ", ".join(empty_fields)

        raise AssertionError(msg)


def ask_specific_input(config: TemplateConfig) -> TemplateConfig:  # noqa: PLR0912
    """
    Ask the user for specific input.

    Parameters
    ----------
    config : TemplateConfig
        The configuration to update.

    Returns
    -------
    TemplateConfig
        The updated configuration.
    """

    def make_options() -> list[str]:
        os.system("clear")
        selections = [
            "I'm finished with the configuration.",
            f"Author name: {config.author_name}",
            f"Author email: {config.author_email}",
            f"Package name: {config.package_name}",
            f"Package module: {config.package_module}",
            f"Package URL: {config.package_url}",
            f"Package description: {config.package_description}",
            f"Package directory: {config.package_dir}",
            f"Include docs: {'Yes' if config.use_docs else 'No'}",
            f"Include tests: {'Yes' if config.use_tests else 'No'}",
            f"Include pre-commit: {'Yes' if config.use_precommit else 'No'}",
            f"Include CI: {'Yes' if config.use_ci else 'No'}",
        ]
        if config.use_ci:
            selections.append(f"Use CI image with JDK: {'Yes' if config.use_java else 'No'}")

        return selections

    reponame_hint = None
    while index := routines.select(
        "What would you like to change? ",
        options=make_options(),
        view_max=13,
    ):
        if index == 0:
            break
        if index == 1:
            _maybe_read_git_user_name(config, force=True)
        elif index == 2:
            _maybe_read_git_user_email(config, force=True)
        elif index == 3:
            _maybe_read_package_name(config, reponame_hint=reponame_hint, force=True)
        elif index == 4:
            _maybe_read_package_module(config, force=True)
        elif index == 5:
            _, reponame_hint = _maybe_ask_repo_url(config, force=True)
        elif index == 6:
            _maybe_ask_package_description(config, force=True)
        elif index == 7:
            _maybe_read_package_dir(config, force=True)
        elif index == 8:
            _maybe_read_use_docs(config, force=True)
        elif index == 9:
            _maybe_read_use_tests(config, force=True)
        elif index == 10:
            _maybe_read_use_precommit(config, force=True)
        elif index == 11:
            _maybe_read_use_ci(config, force=True)
            if config.use_ci:
                _maybe_read_use_java(config, force=True)
        elif index == 12:
            _maybe_read_use_java(config, force=True)

    return config


def resolve_docs_url(config: TemplateConfig) -> str:
    if config.package_url == "bare":
        msg = "Cannot make docs url for a package without git"
        raise ValueError(msg)

    match = _REPO_REGEX.match(config.package_url)

    if not match:
        msg = f"Invalid repository URL {config.package_url}"
        raise ValueError(msg)

    namespace = match.group("namespace")
    reponame = match.group("reponame")

    return _ACC_PY_DOCS_STEM.format(namespace=namespace, reponame=reponame)


def resolve_git_url(config: TemplateConfig) -> str:
    if config.package_url == "bare":
        msg = "Cannot make git url for a package without git"
        raise ValueError(msg)

    match = _REPO_REGEX.match(config.package_url)

    if not match:
        msg = f"Invalid repository URL {config.package_url}"
        raise ValueError(msg)

    namespace = match.group("namespace")
    reponame = match.group("reponame")

    return _GITLAB_HTTPS_STEM.format(namespace=namespace, reponame=reponame)


def resolve_changelog_url(config: TemplateConfig) -> str:
    if config.package_url == "bare":
        msg = "Cannot make changelog url for a package without git"
        raise ValueError(msg)

    match = _REPO_REGEX.match(config.package_url)

    if not match:
        msg = f"Invalid repository URL {config.package_url}"
        raise ValueError(msg)

    namespace = match.group("namespace")
    reponame = match.group("reponame")

    return (
        _GITLAB_HTTPS_STEM.format(namespace=namespace, reponame=reponame)
        + "/-/releases"
    )


def _read_gitconfig(
    gitconfig_path: str | None = None,
) -> dict[str, typing.Any]:
    config = configparser.ConfigParser()

    if gitconfig_path is None:
        # Use the default location of the .gitconfig file
        gitconfig_pth = pathlib.Path("~/.gitconfig").expanduser()
    else:
        gitconfig_pth = pathlib.Path(gitconfig_path)

    config.read(gitconfig_pth)

    # Convert the config object to a dictionary
    return {s: dict(config.items(s)) for s in config.sections() if s == "user"}


def _read_git_user_name(gitconfig_dict: dict[str, typing.Any]) -> str | None:
    if "user" not in gitconfig_dict:
        return None

    return gitconfig_dict["user"].get("name")


def _read_git_user_email(gitconfig_dict: dict[str, typing.Any]) -> str | None:
    if "user" not in gitconfig_dict:
        return None

    return gitconfig_dict["user"].get("email")


def _read_repo_url(repo_url: str) -> tuple[str, str]:
    match = _REPO_REGEX.match(repo_url)
    if not match:
        msg = f"{repo_url} is not a valid CERN gitlab repo"
        raise ValueError(msg)

    namespace = match.group("namespace")
    reponame = match.group("reponame")

    return namespace, reponame


def _maybe_ask_repo_url(
    config: TemplateConfig, *, force: bool = False
) -> tuple[TemplateConfig, str]:
    reponame_hint = ""
    if config.package_url == "" or force:

        def validate_url(url: str) -> None:
            if url == "bare":
                return
            if not _REPO_REGEX.match(url):
                msg = f"{url} is not a valid CERN gitlab repo"
                raise widgets.Abort(msg)

        package_url = routines.input(
            'Gitlab repo URL: (use "bare" to to set up without git) ',
            validate=validate_url,
        )
        config.package_url = package_url
        if package_url != "bare":
            _, reponame_hint = _read_repo_url(package_url)
    elif config.package_url != "bare":
        _, reponame_hint = _read_repo_url(config.package_url)

    return config, reponame_hint


def _maybe_read_git_user_name(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    gitconfig = _read_gitconfig()
    if config.author_name == "" or force:
        default = config.author_name if force else _read_git_user_name(gitconfig) or ""

        author_name = routines.input("Main author name? ", value=default)
        config.author_name = author_name

    return config


def _maybe_read_git_user_email(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    gitconfig = _read_gitconfig()
    if config.author_email == "" or force:

        def validate_email(email: str) -> None:
            if not _EMAIL_REGEX.match(email):
                error = f"{email} is not a valid email address"
                raise widgets.Abort(error)

        if force:
            default = config.author_email
        else:
            default = _read_git_user_email(gitconfig) or ""
        author_email = routines.input(
            "Main author email? ", value=default, validate=validate_email
        )
        config.author_email = author_email

    return config


def _maybe_read_package_name(
    config: TemplateConfig,
    reponame_hint: str | None = None,
    *,
    force: bool = False,
) -> TemplateConfig:
    reponame_hint = reponame_hint or config.package_name
    if config.package_name == "" or force:

        def validate_package_name(name: str) -> None:
            ...

        package_name = routines.input(
            "What is the package name? ",
            validate=validate_package_name,
            value=reponame_hint,
        )
        config.package_name = package_name

    return config


def _maybe_read_package_module(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.package_module == "" or force:

        def validate_package_module(name: str) -> None:
            ...

        default = config.package_name.replace("-", "_")

        package_module = routines.input(
            "What is the package module name? ",
            value=default,
            validate=validate_package_module,
        )
        config.package_module = package_module

    return config


def _maybe_ask_package_description(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.package_description == "" or force:
        limit = 20

        def info(
            widget: widgets.Widget,
            name: str,
            info: typing.Callable[[typing.Any], None],
        ) -> str:
            result = widget.resolve().rstrip("\n")
            remain = limit - len(result)

            if remain < 0:
                return f"+{-remain!s}"

            return f"{remain:2d}"

        def validate_package_description(description: str) -> None:
            if len(description) < limit:
                msg = f"Description is too short. Minimum length is {limit} characters."
                raise widgets.Abort(msg)

        default = config.package_description

        package_description = routines.input(
            "Give a short description of the package: ",
            info=info,
            validate=validate_package_description,
            value=default,
        )

        config.package_description = package_description

    return config


def _maybe_read_package_dir(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.package_dir == pathlib.Path(".") or force:
        if force:
            default_pth = config.package_dir
        else:
            default_pth = pathlib.Path(".").absolute() / config.package_name

        package_dir = routines.input(
            "Where should I initialize the package? ",
            value=os.fspath(default_pth),
        )
        config.package_dir = pathlib.Path(package_dir)

    return config


def _maybe_read_use_docs(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.use_docs is None or force:
        use_docs = routines.inquire("Include documentation skeleton? ", default=True)
        config.use_docs = use_docs

    return config


def _maybe_read_use_tests(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.use_tests is None or force:
        use_tests = routines.inquire("Include tests skeleton? ", default=True)
        config.use_tests = use_tests

    return config


def _maybe_read_use_precommit(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.use_precommit is None or force:
        use_precommit = routines.inquire(
            "Include a pre-commit configuration and initialize? ", default=True
        )
        config.use_precommit = use_precommit

    return config


def _maybe_read_use_ci(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.use_ci is None or force:
        use_ci = routines.inquire("Include an Acc-Py CI configuration? ", default=True)
        config.use_ci = use_ci

    return config


def _maybe_read_use_java(
    config: TemplateConfig, *, force: bool = False
) -> TemplateConfig:
    if config.use_java is None or force:
        use_java = routines.inquire(
            "Use a CI image that supports Java? ", default=False
        )
        config.use_java = use_java

    return config
