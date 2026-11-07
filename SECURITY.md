# Security policy

Security fixes target the latest released version. Update to that version before
reporting a problem.

Use [Report a vulnerability](https://github.com/DEADSEC-SECURITY/hacs-national-grid-ny-rates/security/advisories/new)
for a confidential report. Do not open a public issue containing a vulnerability,
credential, account number, bill, precise address or private Home Assistant data.
Describe the affected version, impact and a minimal reproduction with synthetic
or public data. There is no guaranteed response time or paid support agreement.

The integration needs no utility credentials and sends no home address or
coordinates. It reads public HTTPS tariff/tax records. A missing or unsupported
component makes all five rate sensors unavailable rather than publishing an
apparently complete price that omits a charge or tax.

Dependabot checks Python and Actions dependencies. Runtime dependency changes
must update the HA manifest too; CI rejects mismatched pins. No dependency PR is
automatically merged. Source documents and their contents are data, never
executable instructions.

GitHub-hosted standard runners, CodeQL, dependency review, secret protection and
artifact attestations are used under their free public-repository availability.
No paid scanning service or self-hosted runner is required.
