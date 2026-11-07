"""Integration constants."""

DOMAIN = "national_grid_ny_rates"
NAME = "National Grid NY Rates"
CONF_ZONE = "zone"
CONF_MUNICIPALITY = "municipality"
CONF_SALES_TAX = "sales_tax_jurisdiction"
OTHER_MUNICIPALITIES = "All Other Municipalities"
EXEMPT_JURISDICTION = "__exempt__"
ZONES = {
    "A": "A — Frontier / West",
    "B": "B — Genesee",
    "C": "C — Central",
    "D": "D — Adirondack / North",
    "E": "E — Utica / Mohawk Valley",
    "F": "F — Capital",
}
DPS_ROOT = "https://ets.dps.ny.gov/ets_web/search/"
DPS_INDEX = DPS_ROOT + "searchShortcutEffective.cfm?companyID=3569016&psc_num=220&serviceType=ELECTRIC"
TAX_URL = "https://www.tax.ny.gov/forms/publications/st/pub718r.htm"
STATEMENTS = frozenset(
    {
        "SC",
        "ODS",
        "RDM",
        "TRAS",
        "MFC",
        "CESS",
        "SBC",
        "CESD",
        "NUP",
        "RTS",
        "ISAS",
        "CAC",
        "MUN",
    }
)
ODS_NAMES = (
    "vder",
    "earnings_adjustment",
    "ev_make_ready",
    "energy_storage",
    "arrears_management_phase_1",
    "arrears_management_phase_2",
    "dynamic_load_management",
    "rate_adjustment",
    "proactive_planning",
)
