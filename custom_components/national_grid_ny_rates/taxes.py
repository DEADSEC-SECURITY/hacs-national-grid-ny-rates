"""Residential energy sales tax from NY Publication 718-R, Part 1 only."""

import re
from datetime import date
from decimal import Decimal as D

from bs4 import BeautifulSoup

from .const import EXEMPT_JURISDICTION
from .models import RateError, SalesTax, TaxTable
from .parsers import DATE_PATTERN, clean, parse_date

FRACTIONS = {"¼": D(".25"), "½": D(".5"), "¾": D(".75"), "⅜": D(".375")}


def percentage(value: str) -> D:
    value = clean(value).replace("%", "")
    fraction = D(0)
    if value and value[-1] in FRACTIONS:
        fraction = FRACTIONS[value[-1]]
        value = value[:-1].strip()
    if value and not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise RateError("Unrecognized residential sales tax percentage")
    if not value and not fraction:
        raise RateError("Missing residential sales tax percentage")
    rate = (D(value or "0") + fraction) / 100
    if not 0 <= rate <= D(".20"):
        raise RateError("Residential sales tax percentage is out of range")
    return rate


def parse_sales_taxes(data: bytes, as_of: date) -> TaxTable:
    soup = BeautifulSoup(data, "html.parser")
    heading = soup.find("h1")
    title = clean(heading.get_text()) if heading else ""
    match = re.search(rf"Residential Energy Effective\s+({DATE_PATTERN})", title, re.I)
    if not match:
        raise RateError("Publication 718-R title/effective date is missing")
    effective = parse_date(match[1])
    if effective > as_of:
        raise RateError(f"Residential sales tax publication is future-dated: {effective}")
    part1 = soup.find(lambda tag: tag.name in {"h2", "h3"} and clean(tag.get_text()).startswith("Part 1"))
    if part1 is None or "electricity" not in part1.get_text().lower():
        raise RateError("Residential electricity sales tax table is missing")
    table = part1.find_next("table")
    if table is None:
        raise RateError("Residential electricity sales tax table is missing")
    jurisdictions = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != 2:
            raise RateError("Publication 718-R table columns changed")
        name, value = (clean(cell.get_text(" ", strip=True)) for cell in cells)
        name = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", name))
        if name.lower().startswith("taxing jurisdiction"):
            continue
        if not name or name in jurisdictions:
            raise RateError("Missing or duplicate residential tax jurisdiction")
        jurisdictions[name] = SalesTax(name, percentage(value))
    if len(jurisdictions) < 20:
        raise RateError("Residential sales tax table is incomplete")

    # Temporary exemptions can be in a notice above the table rather than a
    # table row. Never treat the omitted county as exempt beyond that notice.
    notices = []
    for tag in part1.find_all_previous(["p", "li"]):
        text = re.sub(r"\s+,", ",", clean(tag.get_text(" ", strip=True)))
        if "exempt" in text.lower() and "through" in text.lower():
            notices.append(text)
    for text in notices:
        match = re.search(
            rf"^(.+? County)\s*[-–—]\s*Effective ({DATE_PATTERN}),?\s*"
            rf"and continuing through ({DATE_PATTERN}),.*exempt",
            text,
            re.I,
        )
        if not match:
            raise RateError("A temporary residential tax exemption needs review")
        start, end = parse_date(match[2]), parse_date(match[3])
        if start > as_of:
            raise RateError("A future temporary tax exemption needs review")
        name = clean(match[1])
        if name in jurisdictions:
            raise RateError("Temporary tax exemption conflicts with table")
        jurisdictions[name] = SalesTax(name, D(0), end)
    text = clean(soup.get_text(" ", strip=True))
    if "not listed in this publication do not impose a local tax" not in text:
        raise RateError("Residential sales tax exemption rule is missing")
    jurisdictions[EXEMPT_JURISDICTION] = SalesTax(
        "No listed county, city or school-district tax applies",
        D(0),
    )
    return TaxTable(effective, jurisdictions)


def selected_sales_tax(table: TaxTable, jurisdiction: str, as_of: date) -> SalesTax:
    if table.effective > as_of:
        raise RateError("Residential sales tax table is not yet effective")
    if jurisdiction not in table.jurisdictions:
        raise RateError(
            "The selected residential sales tax jurisdiction is no longer listed; reconfigure location"
        )
    selected = table.jurisdictions[jurisdiction]
    if selected.expires is not None and as_of > selected.expires:
        raise RateError(
            "The selected temporary tax exemption expired; waiting for an updated official publication"
        )
    return selected
