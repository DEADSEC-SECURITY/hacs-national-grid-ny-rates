# Contributing

Open an issue or discussion for a substantial change before implementing it.
Keep changes focused and use public rate documents or synthetic data for tests.
Never commit customer invoices, Home Assistant configuration, credentials or
account data. Private research belongs in the ignored .local directory.

Run the checks before opening a pull request:

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python tools/check_repository.py
.venv/bin/ruff check custom_components tests tools
.venv/bin/ruff format --check custom_components tests tools
.venv/bin/yamllint .github .yamllint.yml
.venv/bin/pytest -q --cov=custom_components.national_grid_ny_rates --cov-fail-under=90
.venv/bin/pip-audit --requirement requirements.txt --strict
.venv/bin/python tools/build_release.py --output-dir work/dist
```

Use PRs for changes to main. Required checks must pass; a second maintainer's
approval is not required for this solo-maintained repository. The owner retains
an emergency bypass. Squash merges keep the main branch history linear.

## Dependency updates

Dependabot opens weekly version-update PRs and immediate security-fix PRs when
available. Normal version updates have a three-day cooldown. Major updates stay
separate for review; minor and patch updates are grouped by purpose.

Dependabot understands requirements.txt but not Home Assistant's custom
manifest.json format. For a runtime update, run:

```sh
.venv/bin/python tools/check_repository.py --sync-runtime
```

This copies the reviewed runtime pins into the HA manifest. Commit that change
to the dependency PR, then rerun checks. CI checks both files and blocks a merge
while they disagree. The sync command never installs or executes a package.

## Releases

Update the manifest version in a reviewed PR, merge it, then push the matching
v-prefixed tag. The release workflow tests the tagged code, builds a clean ZIP,
exports an SPDX SBOM, generates checksums and a GitHub build-provenance
attestation, uploads all assets to a draft, then publishes it. Immutability locks
the published assets and tag; fixes require a new version.

Running the Release workflow manually on main tests packaging and attestation
without publishing a release. Private bills, development caches and test fixtures
are excluded from the install ZIP.

HACS validation checks the custom repository; the brands check is omitted because
this project has not submitted a brand to the default HACS catalog. Hassfest and
all other HACS checks still run. This is not an application for catalog inclusion.
