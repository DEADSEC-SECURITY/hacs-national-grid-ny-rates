# Automatic residential electricity tax

This document records the intended implementation. It does not claim the
integration or statewide tax lookup has already been implemented.

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
- Calculate residential sales tax using the matched Part 1 jurisdiction and
  the official taxable-base rules. Verify the treatment of revenue-tax
  surcharges before asserting statewide calculation accuracy.
- Respect the publication's combined jurisdiction rates: for example, a
  school-district row can already include county tax. Do not blindly add that
  row to the county rate again.
- Treat an unlisted locality as exempt only after establishing that no listed
  city or school-district exception applies. Missing or unparsed data is not
  evidence of a zero rate.
- Respect effective dates and temporary exemptions. Check rates daily and
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

Expose fixed monthly service charges separately. Include tax source URLs,
effective dates, jurisdiction names, component percentages and last successful
update in diagnostic attributes. A tax percentage sensor must not pretend that
one RTS percentage applies equally to both supply and delivery.

## Recovery and verification

If official sources cannot be parsed or the location cannot be resolved, do not
publish a newly calculated complete price with omitted taxes. Preserve dated
last-known data with clear availability/staleness behavior, and report the
configuration or source problem.

Before claiming statewide support, test named municipalities, the explicit RTS
outside category, school-district exceptions, combined rates, temporary
exemptions, future effective dates and ambiguous names against independent
official examples. Bill fixtures must be synthetic or public, not private
customer invoices.
