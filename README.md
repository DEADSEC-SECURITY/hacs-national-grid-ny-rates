# National Grid NY Rates

An unofficial Home Assistant integration for National Grid's upstate New York
(Niagara Mohawk) residential electricity rates. No National Grid account required.

**In development.** The public-rate retrieval and calculation have been tested
locally; the Home Assistant integration is being built. This project is not
affiliated with National Grid, HACS, or the New York State government.

## Rate entities

All five rate entities use `USD/kWh`:

| Entity | Includes |
| --- | --- |
| Supply | Electricity supply, reconciliation, clean energy supply, merchant function charge |
| Delivery | Base delivery and the applicable standard delivery adjustments |
| Total before tax | Supply plus delivery |
| Tax | Revenue-tax surcharges and applicable residential sales tax, expressed per kWh |
| Total including tax | Total before tax plus tax; intended for the Energy dashboard |

The fixed monthly service charge is separate. It must not be folded into a
per-kWh rate without an explicit usage assumption.

## Official sources and automatic tax

Rates come from National Grid's public statements and its filings in the
[New York Department of Public Service tariff system](https://ets.dps.ny.gov/ets_web/search/searchShortcutEffective.cfm?companyID=3569016&psc_num=220&serviceType=ELECTRIC).
The regulator's filed Revenue Tax Surcharge statement provides distinct
commodity and delivery tax factors by municipality. These are published
documents, not a documented public JSON tax API.

[New York Publication 718-R](https://www.tax.ny.gov/forms/publications/st/pub718r.htm)
identifies residential energy sales taxes and exemptions. Planned automatic tax
support covers National Grid's upstate New York electric territory, using a
one-time selection of the applicable municipality and residential energy sales-tax
jurisdiction. The percentages then update from official sources. A ZIP code alone
does not reliably identify city, village, county, or school-district boundaries.
Ordinary retail sales-tax rates must not be substituted for residential electricity
tax rates. See [the tax design](docs/tax-design.md).

Target scope: standard residential SC-1 throughout National Grid's upstate New York
electric territory, with configurable load zone and tax jurisdiction. The local
prototype has been checked for Zone C / Central and City of Syracuse; statewide
jurisdiction support remains to be implemented and verified.

Prices are estimates for cost tracking; account-specific credits, alternate
suppliers, time-of-use plans and the final utility bill can differ.

## Development

Keep private bills and account data in the ignored `.local/` directory. Public
tests use official public rate documents or synthetic examples, never customer
invoices.
