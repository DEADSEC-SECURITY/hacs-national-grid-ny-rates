# Local validation — November 7, 2026

Validated before installing anything on the user's Home Assistant system.

## Environment

- Python 3.14.8
- Home Assistant Core 2026.10.4, running through its custom-integration test suite
- Pure Python PDF extraction with pypdf 6.13.2; no external PDF executable
- Automated tests block external network access. Live-source verification is a
  separate explicit run of the same retrieval and calculation code.

## Live official-source result

Zone C / City of Syracuse, standard residential SC-1, no listed residential
sales-tax jurisdiction:

| Entity | USD/kWh |
| --- | ---: |
| Delivery | 0.126104 |
| Supply | 0.07933061775 |
| Total before tax | 0.20543461775 |
| Tax | 0.00470143786109275 |
| Total including tax | 0.21013605561109275 |

The fixed monthly service charge is $19 before tax, or $19.5876282 with the
applicable delivery revenue-tax surcharge, and is excluded from these kWh rates.

The official sources yielded six supply zones, 148 municipal choices and 56
sales-tax choices, including the explicit no-listed-tax option and the current
temporary exemption notice. These counts describe the published tables, not a
geographic verification that every possible pairing is a real service location.

## Automated coverage

Final local result: **58 tests passed**, with **92% line coverage**. Ruff lint,
formatting checks and Git whitespace checks passed.

The suite checks:

- Actual Home Assistant config flow, duplicate prevention, reconfiguration and
  stable entity IDs.
- Exactly five numeric sensors with USD/kWh units and appropriate state classes.
- Six-hour automatic refresh applying a changed sales-tax rate.
- Initial source failures retrying setup; existing sensors becoming unavailable
  together and recovering after a complete successful refresh.
- Current tariff facts for all six supply zones, the MFC formula, adjustments,
  negative credits and fixed-charge separation.
- All parsed municipal choices and all parsed sales-tax choices across all six
  zones, plus independently specified tax arithmetic cases.
- Buffalo's different RTS factors, the explicit outside-municipalities factors,
  school-district combined rates, fractional percentages, temporary-exemption
  expiry and the municipal undergrounding surcharge dates.
- Rejection of PSC 214, nonresidential RTS pages, future filings, incomplete
  components, invalid source URLs and changed/missing tax tables.
- Native retrieval, actual PDF extraction, PDF caching, redirect rejection and
  cancellation of outstanding requests after a failed refresh.

Public fixtures retain their source attribution in
`tests/fixtures/public/sources.json`. No private bill is in the repository.

The integration publishes current tariff rates. It does not reconstruct
historical meter-reading bills or allocate the monthly fixed charge across usage.
Any comparison using private customer records stays local and is excluded from
this repository and its release assets.
