# National Grid NY Rates

[![Tests](https://github.com/DEADSEC-SECURITY/national-grid-ny-rates/actions/workflows/tests.yml/badge.svg)](https://github.com/DEADSEC-SECURITY/national-grid-ny-rates/actions/workflows/tests.yml)
[![Integration validation](https://github.com/DEADSEC-SECURITY/national-grid-ny-rates/actions/workflows/validate.yml/badge.svg)](https://github.com/DEADSEC-SECURITY/national-grid-ny-rates/actions/workflows/validate.yml)
[![Dependency audit](https://github.com/DEADSEC-SECURITY/national-grid-ny-rates/actions/workflows/security-audit.yml/badge.svg)](https://github.com/DEADSEC-SECURITY/national-grid-ny-rates/actions/workflows/security-audit.yml)

An unofficial Home Assistant integration for **National Grid / Niagara Mohawk
standard residential SC-1 electricity in upstate New York**. Retrieves published
supply, delivery adjustments and location-specific taxes without a National Grid
account, invoice upload or API key.

The 0.1.x releases are available through a HACS custom repository.
It is not affiliated with National Grid, New York State, Home Assistant or HACS,
and is not listed in the default HACS catalog.
[Catalog submission #13634](https://github.com/hacs/default/pull/13634) is pending review.

## Five entities

| Entity | Unit | Includes |
| --- | --- | --- |
| Delivery | USD/kWh | Base delivery and all modeled standard delivery adjustments |
| Supply | USD/kWh | Electricity supply, reconciliation, clean energy supply and merchant function charge |
| Total before tax | USD/kWh | Delivery plus supply |
| Tax | USD/kWh | Supply/delivery revenue-tax surcharges and applicable residential sales tax |
| Total including tax | USD/kWh | Complete variable price; select this for the Energy dashboard |

The fixed monthly customer charge is **not** a per-kWh cost. Its before-tax and
after-tax amounts are available in entity attributes, along with component rates,
tax percentages, source links, effective dates and the last successful update.
No usage assumption is used to spread that charge across kWh.

## Coverage and automatic taxes

Supports all six published SC-1 supply regions: A Frontier, B Genesee, C Central,
D Adirondack, E Utica and F Capital.

During setup, select your load zone, municipality and residential energy
sales-tax jurisdiction once. The integration checks the official sources every
six hours and calculates the applicable percentages automatically:

- National Grid's filed **PSC 220 residential Revenue Tax Surcharge** table
  provides distinct supply and delivery factors by city/village and an explicit
  outside-municipalities category.
- New York **Publication 718-R Part 1** provides residential electricity sales
  taxes, including county, city and school-district exceptions and combined rates.
- Filed municipal undergrounding delivery surcharges are applied where relevant.

There is no manually maintained tax percentage. These official published
HTML/PDF records supply the rates; this integration does not depend on a public
JSON tax API.

**ZIP codes do not reliably identify tax boundaries.** Select the legal
jurisdictions that apply to the property. School district boundaries can cross
municipal boundaries. Choose the no-listed-tax option only when no listed county,
city or school district applies; do not use the ordinary retail sales-tax rate.

For **City of Syracuse / Zone C**, choose **City of Syracuse** and **No listed
county, city or school-district tax applies**. Revenue-tax surcharges still apply.

The current public sources contain 148 municipal choices and 56 sales-tax choices,
including the explicit exemption choice. The statewide tax publication also lists
places outside National Grid's electric territory; a listed tax jurisdiction
does not establish that National Grid serves a property.

An expired temporary exemption, unavailable source, missing component or changed
document layout makes the sensors unavailable. A partial price with missing taxes
is never presented as the complete price. Home Assistant retries failed setup;
existing entries retry on refresh. Future effective dates are not applied early.

## Installation

Requires Home Assistant **2026.10 or newer**. Tested locally on Core 2026.10.4
with Python 3.14. Supports Home Assistant OS with no shell commands or add-ons.

1. In HACS, open the menu → **Custom repositories**.
2. Add https://github.com/DEADSEC-SECURITY/national-grid-ny-rates with type **Integration**.
3. Download **National Grid NY Rates** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **National Grid NY Rates**.
5. Select the load zone and tax jurisdictions.
6. In the Energy dashboard, choose **Use an entity with current price** and select **Total including tax** for electricity grid consumption.

To change the location later, open the integration entry's menu and choose
**Reconfigure**. Entity IDs remain stable.

Alternatively, copy only `custom_components/national_grid_ny_rates/` into the
same directory under your Home Assistant configuration and restart before adding
the integration.

## Sources and calculation

Sources are National Grid's public filings in the
[New York Department of Public Service tariff system](https://ets.dps.ny.gov/ets_web/search/searchShortcutEffective.cfm?companyID=3569016&psc_num=220&serviceType=ELECTRIC)
and [NY Publication 718-R](https://www.tax.ny.gov/forms/publications/st/pub718r.htm).
No credentials, address, coordinates or account information are sent.

Supply includes ESCost, ESRM, CESS and the calculated non-demand merchant function
charge. Delivery includes base delivery, LTC, ODS (all nine components), RDM,
TRAS, SBC, CESD, NUP, ISAS, CAC and applicable MUN charges. Revenue-tax factors
are applied separately to supply and delivery; residential sales tax is applied
to the resulting taxable receipts. See [tax calculation details](docs/tax-design.md).

The index and sales-tax publication are retrieved on every refresh. PDF text is
cached locally; statement PDFs are downloaded again after seven days.
DPS returns the entire tariff book for the base leaf. Its extracted SC-1 page is
cached by the leaf's filing ID, so a large download is needed only for first
setup or a changed base-rate filing. PDF parsing runs outside Home Assistant's
event loop. No external PDF executable is required.

These are **current published tariff rates**, not hourly wholesale prices or a
reconstruction of a meter-reading period. Monthly statements use their filed
effective dates. A real bill may prorate some adjustments across a billing period
and round individual charges to cents.

Not supported: ESCO/alternate suppliers, SC-1C or other tariffs, time-of-use plans,
agricultural discounts, net metering/solar, NYPA exceptions, income-based or
account-specific credits, rent allowances, late fees or billing-service fees.
National Grid's downstate New York gas service is outside this electric integration.

## Local development and verification

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check custom_components tests tools
.venv/bin/ruff format --check custom_components tests tools
.venv/bin/pytest -q
```

To retrieve live Syracuse rates using the exact integration code:

```sh
.venv/bin/python tools/check_rates.py \
  --zone C --municipality 'City of Syracuse' --sales-tax __exempt__ \
  --output work/live-rates.json
```

Tests use public official rate documents and synthetic arithmetic examples.
They never upload or publish customer statements. Keep private research in the
ignored `.local/` directory. The only PDF files allowed in Git are the public
test fixtures under `tests/fixtures/public/`.

See the [local validation record](docs/local-validation.md) for the live result,
test environment and coverage.

## Security and maintenance

Dependabot opens Python and GitHub Actions update PRs. CodeQL scans Python and
workflow code, while dependency review and vulnerability audits check dependency
changes. Secret scanning and push protection help prevent credential leaks.
See [SECURITY.md](SECURITY.md) for confidential reports and
[CONTRIBUTING.md](CONTRIBUTING.md) for checks, dependency updates and releases.

New releases are built and tested in GitHub Actions, with a reproducible install
ZIP, SHA256 checksums, an SPDX software bill of materials and a GitHub provenance
attestation. Published releases are immutable. These use standard GitHub-hosted
runners and free features for this public repository.
