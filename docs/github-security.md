# GitHub security and maintenance

This is a public repository using free GitHub features and standard GitHub-hosted
Linux runners. No paid scanner, larger runner, trial or subscription is configured.
Workflow artifacts expire after seven days to limit storage use.

## Repository settings

- Dependabot vulnerability alerts and security-fix PRs.
- Weekly Python and Actions version-update PRs, grouped by purpose, with a
  three-day cooldown for normal updates. Security updates are not delayed.
- Dependency graph and SPDX SBOM export.
- CodeQL default setup with the extended query suite for Python and Actions,
  scanning changes and running periodically.
- Secret scanning and push protection for recognized credentials.
- Private vulnerability reporting through GitHub security advisories.
- Read-only default workflow tokens; workflows cannot approve PR reviews.
- External Actions pinned to full commit SHAs, enforced by GitHub and local CI.
- Squash merges, automatic cleanup of merged branches, and Discussions.
- Main-branch protections requiring PRs and checks, with an owner emergency bypass
  and no requirement for an additional maintainer to approve their own PR.
- Published future releases are immutable.

## Checks and releases

Tests check calculations, configuration flows, unavailable/recovery behavior,
tax updates and repository safeguards. The integration coverage floor is 90%.
Repository checks reject dependency-pin drift, unpinned Actions and accidental
publication of local/private files. Dependency audit resolves and audits runtime
packages and their dependencies; dependency review blocks newly introduced high
or critical vulnerabilities in PRs.

Hassfest checks Home Assistant integration conventions. HACS checks repository
compatibility, excluding only the brand-catalog requirement for this custom
repository. All workflows use ordinary pull_request events with read-only tokens;
none runs untrusted PR code in a privileged pull_request_target workflow.

The release workflow verifies the tag against the integration's manifest version,
runs checks, builds a reproducible integration-only ZIP, exports the repository
SBOM and generates GitHub build-provenance attestations. It uploads all assets to
a draft before publishing, as immutable assets cannot be added or replaced later.
Manual runs on main test the build and attestation without publishing a release.

To verify a downloaded artifact from a release produced by this workflow:

```sh
gh attestation verify national_grid_ny_rates.zip \
  --repo DEADSEC-SECURITY/hacs-national-grid-ny-rates
sha256sum --check SHA256SUMS
```

The original manually published v0.1.0 predates this provenance workflow.
New releases use the workflow above. Runtime dependency PRs need the reviewed
pin copied to the Home Assistant manifest as explained in CONTRIBUTING.md.
