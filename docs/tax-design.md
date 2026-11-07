# Automatic residential electricity tax

This document describes the tax lookup and calculation implemented in version
0.1.0. Jurisdictions are selected during setup; percentages come from current
official documents.

## Coverage

Standard residential electricity supplied by National Grid / Niagara Mohawk in
upstate New York. National Grid's downstate New York gas service is outside this
electricity integration's scope.

Support all applicable locations through configuration rather than hard-coding
Syracuse or one statewide percentage.

## Official sources

1. National Grid's current PSC 220 Revenue Tax Surcharge (RTS) statement in the
   New York Department of Public Service's tariff system. Read only the
   **residential** pages and match the configured city/village, or the statement's
   explicit **All Other Municipalities** category when appropriate. Commodity
   and delivery factors are separate. Do not use PSC 214 outdoor-lighting tables.
2. New York Department of Taxation and Finance Publication 718-R, **Part 1**,
   for residential electricity sales-tax jurisdictions. Parse its current
   effective date, rates, exceptions and temporary exemptions. Do not use Part 2,
   ordinary retail tax tables, solar-PPA tables or nonresidential utility taxes.

Sources are published HTML/PDF records. A documented government JSON API is not
required for automatic rate updates; none has been established for this project.

## One-time location selection

Configuration must identify the rate's load zone and the home's legal tax
jurisdictions. Users select jurisdiction names, not tax percentages.

- Municipality for the RTS factor (city/village, or a verified outside category).
- Applicable residential energy sales-tax jurisdiction, accounting for county,
  city and school district when required.
- Distinguish similarly named places such as City of Syracuse, Village of East
  Syracuse and Village of North Syracuse.

Do not infer all tax jurisdictions from a ZIP code. Home Assistant's home location
may eventually help suggest a match, but ambiguous matches need confirmation.
Do not send a user's address or coordinates to a geocoding service without an
explicitly authorized location-lookup flow.

## Tax selection and calculation

- Apply the RTS commodity factor to applicable supply charges and the RTS
  delivery factor to applicable delivery charges.
- Apply the selected Part 1 sales-tax percentage to supply and delivery
  charges **including** their revenue-tax surcharges. New York's
  [Tax Bulletin ST-860](https://www.tax.ny.gov/pubs_and_bulls/tg_bulletins/st/taxable_receipt.htm)
  explains that taxable receipts include the total charge for taxable services.
  Its excise-tax discussion includes seller-imposed taxes in receipts.
  [TSB-A-98(58)S](https://www.tax.ny.gov/pdf/advisory_opinions/sales/a98_58s.pdf)
  discusses electricity, transportation and surcharges as taxable electric-service
  receipts in a submetering case.
- Total including tax =
  `(supply × (1 + supply RTS) + delivery × (1 + delivery RTS)) × (1 + sales tax)`.
  Tax per kWh is that amount minus the before-tax supply and delivery sum.
- Respect the publication's combined jurisdiction rates: for example, a
  school-district row can already include county tax. Do not blindly add that
  row to the county rate again.
- Treat an unlisted locality as exempt only after establishing that no listed
  city or school-district exception applies. Missing or unparsed data is not
  evidence of a zero rate.
- Respect effective dates and temporary exemptions. Check rates every six hours and
  apply new rates when effective, not when first announced.
- Keep monthly fixed charges and their taxes separate from per-kWh rates.

## Entity contract

All five primary entities report **USD/kWh**:

| Entity | Meaning |
| --- | --- |
| Delivery | Base delivery plus applicable standard delivery adjustments, before tax |
| Supply | Supply plus reconciliation, clean energy supply and merchant function charge, before tax |
| Total before tax | Delivery plus supply |
| Tax | Applicable revenue-tax surcharges and residential sales tax per kWh |
| Total including tax | Total before tax plus tax; suitable for the Energy dashboard's current-price entity |

Expose fixed monthly service charges separately in attributes. Include tax source URLs,
effective dates, jurisdiction names, component percentages and last successful
update in diagnostic attributes. A tax percentage sensor must not pretend that
one RTS percentage applies equally to both supply and delivery.

## Recovery and verification

If official sources cannot be parsed or the location cannot be resolved, make
all five sensors unavailable. Retain the last result and its dated attributes
in memory, report the source/configuration problem, and recover on the next
successful complete refresh. First setup retries rather than creating
apparently usable entities from partial data.

The local test suite checks named municipalities, the explicit RTS
outside category, school-district exceptions, combined rates, temporary
exemptions, future effective dates and ambiguous names against independent
official public rate facts and synthetic arithmetic examples. It also exercises
all six load zones across every parsed municipal choice and every sales-tax
choice. This verifies table coverage and arithmetic; users must still identify
their legal tax jurisdictions correctly. It does not claim every possible
municipality/school-district pairing exists geographically. Fixtures are public,
not private customer invoices.
