# acc-py-maintenance

Automated package maintenance for acc-py projects. Replaces the single-purpose `renovate` CI
job with a composable job that runs Renovate followed by a registry of post-processing steps.

---

## How it works

The CI job runs two things in sequence:

```bash
renovate 2>&1 | tee renovate.log || true
dsb-devtools maintenance run --log renovate.log
```

Renovate opens MRs for dependency updates. The `maintenance run` command then reads the
Renovate log and runs each registered step. Steps that do not need Renovate output (e.g.
deprecation warnings) run unconditionally. Steps that do (e.g. cascade patching) are skipped
if Renovate produced no output.

---

## Setting up in a project

Run the interactive setup from your project root:

```bash
dsb-devtools renovate setup
```

This writes `.gitlab/renovate.gitlab-ci.yml` (the job template), adds an `acc-py-maintenance`
job to `.gitlab-ci.yml`, sets the `RENOVATE_TOKEN` CI variable, and creates a pipeline
schedule.

In your `.gitlab-ci.yml` the job looks like:

```yaml
include:
  - local: .gitlab/renovate.gitlab-ci.yml

acc-py-maintenance:
  extends: .acc-py-maintenance
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
    - when: never
```

---

## The maintenance image

The job runs in `registry.cern.ch/dsb-devtools/renovate:<tag>`, built from
`.gitlab/Dockerfile.renovate`. It extends the official `renovate/renovate` image and adds:

- CERN root and intermediate CA certificates
- `dsb-devtools` (from the acc-py registry) — provides the `maintenance` subcommand
- `setup-py-migrator` (from the acc-py registry) — used by post-upgrade hooks

### Building the image

Image tags follow the `YYYY.MM` scheme. The mapping from internal tag to upstream Renovate
tag is in `.gitlab/renovate-versions.yml`.

```bash
# Build locally (requires Docker)
RENOVATE_TAG=$(grep 'renovate_tag' .gitlab/renovate-versions.yml | awk '{print $2}')
docker build \
  --build-arg RENOVATE_TAG=$RENOVATE_TAG \
  -t registry.cern.ch/dsb-devtools/renovate:2026.04 \
  -f .gitlab/Dockerfile.renovate \
  .

# Push
docker push registry.cern.ch/dsb-devtools/renovate:2026.04
```

To update `dsb-devtools` or `setup-py-migrator` in the image, bump the internal tag in
`.gitlab/renovate-versions.yml` and rebuild.

---

## Running upgrades offline (dry run)

### Full pipeline dry run (Renovate + maintenance steps)

```bash
docker run --rm \
  -e RENOVATE_TOKEN=$RENOVATE_TOKEN \
  -e RENOVATE_PLATFORM=gitlab \
  -e RENOVATE_ENDPOINT=https://gitlab.cern.ch/api/v4 \
  -e RENOVATE_REPOSITORIES=dsb/hysteresis/sa-preisach \
  -e RENOVATE_AUTODISCOVER=false \
  -e LOG_FORMAT=json \
  -e LOG_LEVEL=debug \
  -e RENOVATE_DRY_RUN=full \
  registry.cern.ch/dsb-devtools/renovate:2026.04 \
  sh -c 'renovate 2>&1 | tee renovate.log || true && dsb-devtools maintenance run --log renovate.log --dry-run'
```

`RENOVATE_DRY_RUN=full` tells Renovate to make no changes (no MRs, no branches).
`--dry-run` tells the maintenance steps to make no API calls or git pushes.

### Maintenance steps only (from an existing log)

If you already have a Renovate log file:

```bash
dsb-devtools maintenance run --log renovate.log --dry-run
```

### Inspect what Renovate found

```bash
dsb-devtools maintenance parse-log --log renovate.log
```

Prints a JSON summary of all branches Renovate considered, with per-branch upgrade details
(package name, current/new version, update type, MR number).

---

## Deprecation manifest

`dsb_devtools/maintenance/manifest.json` defines the known acc-py base distributions:

```json
{
  "latest": "2026.01",
  "base_distributions": {
    "2026.01": {"python": "3.14", "eol": "2031-01-01"},
    "2023.06": {"python": "3.11", "eol": "2027-12-01"},
    "2021.12": {"python": "3.9",  "eol": "2026-12-01", "deprecated": true},
    "2020.11": {"python": "3.7",  "eol": "2026-12-01", "deprecated": true}
  },
  "packages": {}
}
```

- `latest` — the recommended tag; used in upgrade messages
- `deprecated: true` — explicitly EOL, set in the manifest
- urgent — derived at runtime: EOL within 6 months and not deprecated

At runtime the manifest is fetched from a live URL first (configurable via
`MAINTENANCE_MANIFEST_URL` env var or `--manifest` flag). On any network or parse failure it
falls back to the bundled copy with a loud stderr warning.

To update EOL dates or add new distributions, edit `manifest.json` and rebuild the image.
The live URL (when configured) can be updated without a rebuild.

---

## Maintenance steps

Steps are registered in `dsb_devtools/maintenance/_steps.py`. Each step implements:

```python
class MyStep(MaintenanceStep):
    name = "my-step"
    requires_renovate_output = False  # or True

    def run(self, ctx: StepContext) -> None:
        ...
```

Steps with `requires_renovate_output = True` are skipped when no log file is provided or
when the log contains no parseable output (e.g. Renovate crashed before completing).

### Current steps

| Step | Trigger | What it does |
|------|---------|--------------|
| `base-dist` | always | Warns if `ACC_PY_BASE_IMAGE_TAG` in `.gitlab-ci.yml` is deprecated or approaching EOL |

### Adding a new step

1. Create `dsb_devtools/maintenance/steps/my_step.py` with a `MyStep` class
2. Add `MyStep()` to `STEPS` in `dsb_devtools/maintenance/_steps.py`
3. If the step needs a tool at runtime, install it in `Dockerfile.renovate` and bump the image tag

---

## Post-upgrade hooks

Renovate supports `postUpgradeTasks` — shell commands that run after a dependency is bumped,
before the commit is created. Any files modified by the commands are committed alongside the
version bump.

`setup-py-migrator` is installed in the image at `/usr/local/bin/` and can be used as a
post-upgrade hook to migrate `setup.py` → `pyproject.toml` when Renovate opens an MR on a
repo that still uses `setup.py`.

To enable it, add to `renovate.json`:

```json
{
  "postUpgradeTasks": {
    "commands": ["setup-py-migrator"],
    "fileFilters": ["pyproject.toml", "setup.py", "setup.cfg"],
    "executionMode": "branch"
  }
}
```

And register the command in the self-hosted Renovate config under
`allowedPostUpgradeCommands`.
