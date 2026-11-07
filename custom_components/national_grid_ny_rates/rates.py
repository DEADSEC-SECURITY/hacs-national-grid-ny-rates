"""Calculate the current standard SC-1 variable price without fitting bills."""

from datetime import date
from decimal import Decimal as D

from .const import ODS_NAMES, OTHER_MUNICIPALITIES, STATEMENTS, TAX_URL, ZONES
from .models import Catalog, RateBook, RateError, RateResult
from .parsers import base_rates, line_values, municipal_surcharges, revenue_taxes, supply_rates
from .taxes import selected_sales_tax


def catalog(book: RateBook) -> Catalog:
    municipalities = set(revenue_taxes(book.statements["RTS"]))
    municipalities.update(municipal_surcharges(book.statements["MUN"]))
    return Catalog(tuple(sorted(municipalities)), book.sales_taxes.jurisdictions)


def calculate(book: RateBook, zone: str, municipality: str, jurisdiction: str, as_of: date) -> RateResult:
    if zone not in ZONES:
        raise RateError("Unsupported load zone; choose A through F")
    if missing := STATEMENTS - book.statements.keys():
        raise RateError(f"Missing required adjustments: {', '.join(sorted(missing))}")
    for doc in [book.base, *book.statements.values()]:
        if doc.effective > as_of:
            raise RateError("A selected tariff filing is not yet effective")
    docs = book.statements
    monthly, delivery_base = base_rates(book.base)
    cost, esrm, ltc = supply_rates(docs["SC"], zone)
    cess = line_values(docs["CESS"].text, r"^\s*All service classifications")[-1]
    mf = docs["MFC"].text
    uncollectible = line_values(mf, r"Electricity Supply Un\s*collectible Expense Factor", 2)[0] / 100
    working = line_values(mf, r"Working Capital on\s*Purchased Power Costs Factor", 2)[0] / 100
    procurement = line_values(mf, r"Electricity Supply Procurement Charge", 2)[0]
    collection = line_values(mf, r"Electricity Supply Credit and Collection Charge", 2)[0]
    mfc = (cost + esrm + cess) * uncollectible + (cost + esrm) * working + procurement + collection
    ods = line_values(docs["ODS"].text, r"^\s*SC1\s", len(ODS_NAMES))
    supply_components = {
        "electricity_supply": cost,
        "supply_reconciliation": esrm,
        "clean_energy_supply": cess,
        "merchant_function": mfc,
    }
    delivery_components = {
        "base_delivery": delivery_base,
        "legacy_transition": ltc,
        "other_delivery_surcharges": sum(ods),
        "revenue_decoupling": line_values(docs["RDM"].text, r"^\s*S\.C\. No\. 1 and")[-1],
        "transmission_adjustment": line_values(docs["TRAS"].text, r"^\s*SC1\s")[0],
        "system_benefits": line_values(docs["SBC"].text, r"^\s*SC1\s")[-1],
        "clean_energy_delivery": line_values(docs["CESD"].text, r"^\s*All service classifications")[-1],
        "net_utility_plant": line_values(docs["NUP"].text, r"^\s*SC1\s")[0],
        "incremental_state_assessment": line_values(docs["ISAS"].text, r"^\s*SC1\s")[0],
        "commodity_adjustment": line_values(docs["CAC"].text, r"Service Classification Nos\. 1 and 1C")[-1],
    }
    municipal = municipal_surcharges(docs["MUN"])
    rts = revenue_taxes(docs["RTS"])
    if municipality not in rts and municipality not in municipal:
        raise RateError("Municipality is no longer listed; reconfigure location")
    delivery_components["municipal_undergrounding"] = D(0)
    if municipality in municipal:
        value, start, end = municipal[municipality]
        if start <= as_of <= end:
            delivery_components["municipal_undergrounding"] = value
    supply_factor, delivery_factor = rts.get(municipality, rts[OTHER_MUNICIPALITIES])
    sales_tax = selected_sales_tax(book.sales_taxes, jurisdiction, as_of)
    supply = sum(supply_components.values())
    delivery = sum(delivery_components.values())
    before_tax = supply + delivery
    supply_revenue_tax = supply * supply_factor
    delivery_revenue_tax = delivery * delivery_factor
    revenue_tax = supply_revenue_tax + delivery_revenue_tax
    # Receipts include the utility's revenue tax surcharge; the residential
    # sales tax is then applied to those receipts. See docs/tax-design.md.
    sales_amount = (before_tax + revenue_tax) * sales_tax.rate
    tax = revenue_tax + sales_amount
    attributes = {
        "service_class": "SC-1 standard residential",
        "load_zone": zone,
        "municipality": municipality,
        "sales_tax_jurisdiction": sales_tax.label,
        "sales_tax_percent": float(sales_tax.rate * 100),
        "sales_tax_exemption_expires": sales_tax.expires.isoformat() if sales_tax.expires else None,
        "supply_revenue_tax_percent": float(supply_factor * 100),
        "delivery_revenue_tax_percent": float(delivery_factor * 100),
        "supply_components_usd_per_kwh": {k: float(v) for k, v in supply_components.items()},
        "delivery_components_usd_per_kwh": {k: float(v) for k, v in delivery_components.items()},
        "other_delivery_components_usd_per_kwh": dict(zip(ODS_NAMES, map(float, ods), strict=True)),
        "tax_components_usd_per_kwh": {
            "supply_revenue_tax": float(supply_revenue_tax),
            "delivery_revenue_tax": float(delivery_revenue_tax),
            "residential_sales_tax": float(sales_amount),
        },
        "monthly_service_charge_usd_before_tax": float(monthly),
        "monthly_service_charge_usd_including_tax": float(
            monthly * (1 + delivery_factor) * (1 + sales_tax.rate)
        ),
        "fixed_charge_included_in_kwh_price": False,
        "last_successful_update": book.fetched_at.isoformat(),
        "source_urls": {
            "base_tariff": book.base.url,
            "residential_sales_tax": TAX_URL,
            **{code: doc.url for code, doc in docs.items()},
        },
        "effective_dates": {
            "base_tariff": book.base.effective.isoformat(),
            "residential_sales_tax": book.sales_taxes.effective.isoformat(),
            **{code: doc.effective.isoformat() for code, doc in docs.items()},
        },
    }
    return RateResult(delivery, supply, before_tax, tax, before_tax + tax, attributes)
