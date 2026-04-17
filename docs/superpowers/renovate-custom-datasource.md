# Renovate custom datasource for Acc-Py base image

## Goal

Automatically open MRs when a new Acc-Py base image tag is released. A single image tag bump
implies a cascade of changes across the repo:

- `ACC_PY_BASE_IMAGE_TAG` in `.gitlab-ci.yml`
- `PY_VERSION` in `.gitlab-ci.yml`
- `requires-python` in `pyproject.toml`
- `target-version` in `[tool.ruff]` and `[tool.ruff.format]`
- `target-version` in `[tool.black]`
- `Programming Language :: Python :: 3.X` classifiers in `pyproject.toml`
- `python_version` in `[tool.mypy]` if set

The image tag (`2023.06`) and the Python version it ships (`3.11`) are coupled but not the same
string — Renovate cannot derive one from the other without an explicit mapping.

## How it would work

Renovate supports two mechanisms that compose into a solution:

### 1. Custom manager (regex)

A custom manager uses a regex to extract a dependency name and current version from any file.
Example targeting `.gitlab-ci.yml`:

```json
{
  "managerName": "regex",
  "fileMatch": ["(^|/).gitlab-ci.yml$"],
  "matchStrings": [
    "ACC_PY_BASE_IMAGE_TAG:\\s*[\"'](?<currentValue>[\\d.]+)[\"']"
  ],
  "depNameTemplate": "acc-py-base",
  "datasourceTemplate": "custom.acc-py-base"
}
```

This tells Renovate: "find the current value of `ACC_PY_BASE_IMAGE_TAG` and treat it as
a dependency called `acc-py-base`, looked up via a custom datasource."

### 2. Custom datasource

A custom datasource is a URL that Renovate fetches to get available versions.
Renovate supports several response formats — the simplest is a JSON endpoint returning
a list of versions:

```json
{
  "releases": [
    { "version": "2023.06" },
    { "version": "2024.01" }
  ]
}
```

This endpoint needs to be hosted somewhere Renovate can reach. Options:

- **GitLab tags API** — if the Acc-Py base image is versioned as tags on a GitLab repo,
  Renovate's built-in `gitlab-tags` datasource works out of the box (no custom datasource needed).
- **Nexus/PyPI index** — if base image versions are published as a package on the Acc-Py
  Nexus index, the `pypi` datasource can be used directly.
- **Custom JSON endpoint** — a small static file or CI-generated artifact hosted on
  `acc-py.web.cern.ch` listing available versions. Renovate fetches it on each run.
- **HTML scraping** — Renovate's `html` datasource can scrape a version listing page
  using an XPath selector, if a human-readable page already exists.

## The cascade problem

The image tag (`2023.06`) and the Python version (`3.11`) are different strings that must change
together. Renovate handles this in two realistic ways:

### Option A — Renovate detects, CI cascades

Renovate opens an MR updating only `ACC_PY_BASE_IMAGE_TAG`. A CI job in that MR reads the new
tag, looks up the corresponding Python version, and patches `PY_VERSION`, `pyproject.toml`,
`ruff`, `black`, and `mypy` config automatically. The MR is then ready for maintainer review
as a complete, consistent update.

This requires a mapping from image tag → Python version to be available somewhere (see below).

### Option B — Grouped regex managers

Define a separate regex custom manager for each occurrence of the version string, all sharing
the same `depName` and `groupName` so they land in one MR. This works cleanly for fields where
the version string is identical (e.g. `PY_VERSION: "3.11"` and `requires-python = "~=3.11"`),
but breaks for `ACC_PY_BASE_IMAGE_TAG` since its format differs from the Python version.

A hybrid is possible: Option B for the Python version string across all files, plus Option A
for the image tag → Python version derivation.

**Option A is recommended** — it keeps `renovate.json` simple and puts the cascade logic where
it belongs (CI), not in Renovate config.

## What we need to know first

Before implementing, we need to answer:

1. Where is the mapping from Acc-Py image tag to Python version published?
   The acc-py-gitlab-ci-templates repo likely documents this — check
   https://gitlab.cern.ch/acc-co/devops/python/acc-py-gitlab-ci-templates for a changelog,
   release notes, or a machine-readable file listing `image_tag → python_version`.
2. Where are Acc-Py base image versions authoritatively listed?
   (GitLab tags, Nexus, a web page, something else?)
3. Is the version format always `YYYY.MM`, or can it have patch components?
4. Should Renovate propose any new tag, or only stable/non-pre-release ones?

## Implementation in `renovate.json`

Once the datasource URL is known, the config would look like:

```json
{
  "customManagers": [
    {
      "managerName": "regex",
      "fileMatch": ["(^|/).gitlab-ci.yml$"],
      "matchStrings": [
        "ACC_PY_BASE_IMAGE_TAG:\\s*[\"'](?<currentValue>[\\d.]+)[\"']"
      ],
      "depNameTemplate": "acc-py-base",
      "datasourceTemplate": "custom.acc-py-base",
      "versioningTemplate": "loose"
    }
  ],
  "customDatasources": {
    "acc-py-base": {
      "defaultRegistryUrlTemplate": "https://<endpoint-url>",
      "format": "json"
    }
  }
}
```

This would be added to `renovate.json` (generated by `write_renovate_json`) and exposed
as a flag in `RenovateConfig` (e.g. `acc_py_base: bool = False`) once the datasource
URL is confirmed.

## Custom Renovate image

The custom Renovate image is hosted at `registry.cern.ch/dsb-devtools/renovate` and extends
the official `renovate/renovate` image with:

- CERN root and intermediate CA certificates (PEM format, baked in at build time)
- `setup-py-migrator` from `https://gitlab.cern.ch/acc-co/devops/python/incubator/setup_py_migrator`
- Any other post-upgrade hook tools, installed at `/opt/acc-py/hooks/`

Image versioning uses dated tags (e.g. `2026.04`). The mapping from internal tag to upstream
Renovate tag is tracked in `.gitlab/renovate-versions.yml`.

## Post-upgrade hooks

Renovate supports `postUpgradeTasks` — shell commands that run after a dependency is bumped
but before the commit is created. Any files modified by the commands are committed alongside
the version change (controlled by `fileFilters`). This is the mechanism for running custom
migration logic as part of a Renovate MR.

### What hooks can do

- Modify files in the repository (e.g. migrate `setup.py` → `pyproject.toml`)
- Read upgrade context via `dataFileTemplate` + `$RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE`
- Run any tool baked into the image at `/opt/acc-py/hooks/`

### What hooks cannot do

- Modify the MR title or description — `prBodyNotes` and other PR body options use Handlebars
  templates evaluated by Renovate itself, not by hook scripts. There is no mechanism to inject
  hook output into the MR body.
- Open new MRs or comment on existing ones — hooks run in the Renovate process, not as a
  separate GitLab actor.

### Current hooks

| Hook | Trigger condition | Tool |
|------|-------------------|------|
| `setup-py` maintenance step | `setup.py` exists in the repo (detected by `setup-py-migrator`) | `SetupPyStep` in `dsb_devtools/maintenance/steps/setup_py.py` |

Each hook is registered in `allowedPostUpgradeCommands` in the self-hosted Renovate config
and in `postUpgradeTasks.commands` in `renovate.json`.

### Adding new hooks

New migration tools should be added as `MaintenanceStep` implementations in
`dsb_devtools/maintenance/steps/` and registered in `dsb_devtools/maintenance/_steps.py`.
Add the tool as a dependency of `dsb-devtools` in `pyproject.toml` — it will be available
in the Renovate image automatically.

## Separate bot pipeline for MR enrichment

Because `postUpgradeTasks` cannot modify the MR description, any enrichment that requires
writing to the MR (deprecation warnings, EOL notices, migration summaries) needs a separate
pipeline that runs as a GitLab actor.

The approach:

- A GitLab CI job (separate from the Renovate job) triggers on MR events or on a schedule
- It uses the same `RENOVATE_TOKEN` (or a dedicated service account token) with `api` scope
  to call the GitLab MR API and post notes or update the description
- It can read the Renovate branch, inspect changed files, and run checks against internal
  package registries or deprecation manifests

This keeps Renovate's role narrow (open the MR with correct file changes) and puts
GitLab-aware logic in a place that can actually use the GitLab API — a normal CI job with
a token.

The `RENOVATE_TOKEN` already has the required scopes (`api`, `read_repository`,
`write_repository`) and is available as a CI variable, making it a natural candidate for
reuse in this bot pipeline without introducing a new credential.
