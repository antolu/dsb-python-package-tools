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

====================
acc-py-maintenance
====================

The :code:`acc-py-maintenance` CI job keeps Acc-Py packages up to date. It runs Renovate to
open dependency-update MRs, then runs a series of maintenance steps that act on the Renovate
output. Both run in the same CI job on a schedule.

What it does
------------

On every scheduled run:

- **Dependency updates** — Renovate opens or updates MRs for outdated Python dependencies
  (:code:`pyproject.toml`), pre-commit hook revisions, and git submodule tags. Updates are
  never auto-merged unless :code:`RENOVATE_AUTOMERGE=true` is set.

- **Base distribution deprecation check** — if the project's :code:`ACC_PY_BASE_IMAGE_TAG` in
  :code:`.gitlab-ci.yml` refers to a deprecated or soon-to-expire Acc-Py base image, a warning
  is posted to the Dependency Dashboard issue.

- **setup.py migration** — if the project still has a :code:`setup.py`, it is automatically
  migrated to :code:`pyproject.toml` and committed to the Renovate-managed branch.

Prerequisites
-------------

- A GitLab access token with :code:`api`, :code:`read_repository`, and :code:`write_repository`
  scopes (PAT, project token, or group token)
- The token owner must have **Maintainer** role on the project

Setup
-----

Run the setup command from inside the project's git checkout:

::

    dsb-renovate setup

This writes :code:`renovate.json`, creates a CI pipeline schedule, and sets the
:code:`RENOVATE_TOKEN` CI variable on the project. The command auto-detects the GitLab project
from the current git remote. The token is read from :code:`--token`, or falls back to the
:code:`RENOVATE_TOKEN` / :code:`GITLAB_TOKEN` environment variables, or prompts interactively.

Other commands:

::

    dsb-renovate update     # update the existing schedule
    dsb-renovate teardown   # remove the schedule and optionally the CI variable

Integration with dsb-pkginit
-----------------------------

When running :code:`dsb-pkginit` with CI enabled and a real GitLab URL, the tool will offer to
run :code:`dsb-renovate setup` at the end of package initialization.

CI variables
------------

Required:

- :code:`RENOVATE_TOKEN` — GitLab access token (scopes: :code:`api`, :code:`read_repository`, :code:`write_repository`)

Optional:

- :code:`RENOVATE_AUTOMERGE` — set to :code:`"true"` to enable automerge for Renovate MRs (default: disabled)
- :code:`RENOVATE_IMAGE_TAG` — internal Renovate image tag to use (default: :code:`2026.04`)
- :code:`MAINTENANCE_MANIFEST_URL` — URL or path to a custom deprecation manifest JSON (default: bundled)

Reusing the CI template
------------------------

The job template is defined in :code:`.gitlab/renovate.gitlab-ci.yml`. To include it in another
project:

.. code-block:: yaml

    include:
      - project: dsb/devops/devtools
        file: .gitlab/renovate.gitlab-ci.yml

    my_maintenance:
      extends: .acc-py-maintenance

The :code:`RENOVATE_TOKEN` CI variable must be set on the project (or inherited from a group variable).

Renovate image
--------------

The job runs from a custom Docker image at :code:`registry.cern.ch/dsb-devtools/renovate`.
It extends the official :code:`renovate/renovate` image with CERN CA certificates and
:code:`dsb-devtools` pre-installed (which includes :code:`setup-py-migrator` as a dependency).

Image versioning uses dated tags (e.g. :code:`2026.04`). The mapping from internal tag to
upstream Renovate tag is tracked in :code:`.gitlab/renovate-versions.yml`:

.. code-block:: yaml

    # Maps internal release tags to upstream Renovate image tags
    2026.04: "43.111-full"

To release a new image version:

1. Add a new entry to :code:`.gitlab/renovate-versions.yml`
2. Trigger :code:`build_renovate_image` manually in GitLab CI (set :code:`INTERNAL_TAG` to the new tag),
   or build locally:

::

    .gitlab/build-renovate-image.sh 2026.04

The script requires :code:`docker` and :code:`yq`, and you must be logged in to :code:`registry.cern.ch`.

Local dry run
-------------

To run Renovate only (no maintenance steps), without opening any MRs:

.. code-block:: bash

    docker run --rm \
        -e RENOVATE_TOKEN=<your-token> \
        -e RENOVATE_PLATFORM=gitlab \
        -e RENOVATE_ENDPOINT=https://gitlab.cern.ch/api/v4 \
        -e RENOVATE_REPOSITORIES=<org>/<repo> \
        -e RENOVATE_AUTODISCOVER=false \
        -e LOG_LEVEL=debug \
        -e RENOVATE_DRY_RUN=full \
        registry.cern.ch/dsb-devtools/renovate:2026.04 \
        renovate

To run the full pipeline — Renovate followed by all maintenance steps — in dry-run mode:

.. code-block:: bash

    docker run --rm \
        -e RENOVATE_TOKEN=<your-token> \
        -e RENOVATE_PLATFORM=gitlab \
        -e RENOVATE_ENDPOINT=https://gitlab.cern.ch/api/v4 \
        -e RENOVATE_REPOSITORIES=<org>/<repo> \
        -e RENOVATE_AUTODISCOVER=false \
        -e LOG_FORMAT=json -e LOG_LEVEL=debug \
        -e RENOVATE_DRY_RUN=full \
        registry.cern.ch/dsb-devtools/renovate:2026.04 \
        sh -c 'renovate 2>&1 | tee /tmp/renovate.log || true && dsb-devtools maintenance run --log /tmp/renovate.log --dry-run'

The :code:`--dry-run` flag makes maintenance steps print what they would do without making any
API calls or git pushes. To run maintenance steps against an existing log file without Docker:

::

    dsb-devtools maintenance run --log renovate.log --dry-run

To inspect the parsed Renovate log as JSON:

::

    dsb-devtools maintenance parse-log --log renovate.log
