Package usage
=============

The DSB devtools package is a convenience package for BE-CSS-DSB section to consolidate Python devops.

The package is installable from Acc-Py as

::

    pip install dsb-devtools

If your pip is not yet configured to use the Acc-Py repository, you can add the repository to your pip configuration by running

::

    pip install git+https://gitlab.cern.ch/acc-co/devops/python/acc-py-pip-config.git

=============
Package usage
=============

The main use of the package is the :code:`dsb-pkginit` entrypoint, which is equivalent to :code:`python -m dsb_devtools.pkginit`.
Or similarly the :code:`dsb-devtools pkginit` command, or :code:`python -m dsb_devtools pkginit`.

Creating a new package
----------------------

The :code:`dsb-pkginit` command / entrypoint is used to initialize a new Python package.
It creates a new directory with the package name, and initializes a new git repository in it.

The recommended way of using it is to first create a GitLab project, and then run :code:`dsb-pkginit`
to read the project URL and initialize the package with the correct remote, and inferred package name.

What does it do?
----------------

The DSB package initialization tool uses the template available at
https://gitlab.cern.ch/dsb/devops/python-package-template
to create a new Python package (skeleton). The template includes the following features:

- A basic Python package structure
    - A pyproject.toml file
    - Package versioning based on setuptools_scm
    - Linter and formatter configuration for black and ruff
    - Type checking with mypy
- A GitLab CI/CD pipeline
- A documentation skeleton for Acc-Py documentation with Sphinx
- A tests skeleton with pytest
- Pre-commit hooks with ruff, mypy and generic pre-commit hooks
- .gitignore file

For details on Acc-Py, see https://confluence.cern.ch/display/ACCPY/Getting+started+with+Acc-Py

Configuration options
----------------------

The :code:`dsb-pkginit` command has a few options to customize the package initialization. The main flags are

- :code:`--no-ci`  - Do not initialize / create the GitLab CI/CD pipeline
- :code:`--no-docs` - Do not initialize / create documentation skeleton
- :code:`--no-tests` - Do not initialize / create tests skeleton
- :code:`--no-precommit` - Do not initialize / create pre-commit hooks

These flags can also be set during the interactive initialization process, but these flags
are provided as a convenience to set the defaults used in the interactive process.

Additional flags are available, see :code:`dsb-pkginit --help` for more information.

Creating a package without interactive mode
--------------------------------------------

The :code:`dsb-pkginit` command can also be used in non-interactive mode, by providing the required arguments
as command line arguments. All the below arguments must be provided, as well as the :code:`--no-confirm` flag.
The command line arguments are

- :code:`--package-name` - The name of the package
- :code:`--package-module` - The main module of the package
- :code:`--url` - The URL of the GitLab project
- :code:`--author` - The name of the author
- :code:`--email` - The email of the author
- :code:`--description` - The description of the package
- :code:`--package-dir` - The directory to create the package in

In addition to the above, the flags :code:`--no-ci`, :code:`--no-docs`, :code:`--no-tests`, :code:`--no-precommit` can be used to disable the respective features.

Example usage
-------------

::

    dsb-pkginit --no-precommit

=============
Run on the TN
=============

dsb-pkginit is also deployed on the TN Acc-Py distribution, runnable as

::

    acc-py app run dsb-devtools pkginit

================
Renovate setup
================

The :code:`dsb-renovate` entrypoint sets up `Renovate <https://docs.renovatebot.com/>`_ for automated
dependency update MRs on a GitLab project. Renovate runs as a self-hosted CI job — no external
service is used.

The following are managed automatically:

- Python dependencies in :code:`pyproject.toml` (pep621 manager)
- Pre-commit hook revisions and :code:`additional_dependencies` in :code:`.pre-commit-config.yaml`
- Git submodule tags (semver versioning)

Renovate never auto-merges. All updates are opened as MRs for human review.

Prerequisites
-------------

- A GitLab access token with :code:`api` scope (PAT, project token, or group token)
- The token owner must have **Maintainer** role on the project (required to create CI variables and pipeline schedules)

Commands
--------

Set up Renovate for a project (writes :code:`renovate.json`, creates CI schedule, sets :code:`RENOVATE_TOKEN`):

::

    dsb-renovate setup

Update an existing Renovate schedule:

::

    dsb-renovate update

Remove the Renovate schedule and optionally the CI variable:

::

    dsb-renovate teardown

All commands auto-detect the project from the current git remote. The token is read from
:code:`--token`, or falls back to the :code:`RENOVATE_TOKEN` / :code:`GITLAB_TOKEN` environment variables,
or prompts interactively.

Integration with dsb-pkginit
-----------------------------

When running :code:`dsb-pkginit` with CI enabled and a real GitLab URL, the tool will offer to run
:code:`dsb-renovate setup` at the end of package initialization. The Renovate manager options
(pyproject, pre-commit, submodules) appear in the configuration summary table and can be
adjusted before confirming.

Reusing the CI template
------------------------

The Renovate CI job is defined in :code:`.gitlab/renovate.gitlab-ci.yml`. To reuse it in another
project, include the file and extend the hidden job:

.. code-block:: yaml

    include:
      - project: dsb/devops/devtools
        file: .gitlab/renovate.gitlab-ci.yml

    my_renovate:
      extends: .renovate

The :code:`RENOVATE_TOKEN` CI variable must be set on the project (or inherited from a group variable).

Renovate image
--------------

Renovate runs from a custom Docker image hosted at
:code:`registry.cern.ch/dsb-devtools/renovate`. The image extends the official
:code:`renovate/renovate` image with the CERN root and intermediate CA certificates pre-installed,
so it can reach internal services like :code:`acc-py-repo.cern.ch`.

Image versioning uses dated tags (e.g. :code:`2026.04`, :code:`2026.04.1` for patches).
The mapping from internal tag to upstream Renovate tag is tracked in
:code:`.gitlab/renovate-versions.yml`:

.. code-block:: yaml

    # Maps internal release tags to upstream Renovate image tags
    2026.04: "43.110.14-full"

To release a new image version:

1. Add a new entry to :code:`.gitlab/renovate-versions.yml`
2. Either trigger :code:`build_renovate_image` manually in GitLab CI (set :code:`INTERNAL_TAG` to the new tag),
   or build locally:

::

    .gitlab/build-renovate-image.sh 2026.04

The script requires :code:`docker` and :code:`yq`, and you must be logged in to
:code:`registry.cern.ch`.
