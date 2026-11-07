"""Strict parsers for public PSC 220 residential tariff filings."""

import re
from datetime import date, datetime
from decimal import Decimal as D
from io import BytesIO
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .const import DPS_ROOT, OTHER_MUNICIPALITIES, STATEMENTS
from .models import Document, RateError

NUMBER = re.compile(r"\(?-?\$?\d+\.\d+\)?")
DATE_PATTERN = r"[A-Za-z]+\s+\d{1,2},\s*\d{4}"


def clean(value: str) -> str:
    return " ".join(value.split())


def parse_date(value: str) -> date:
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(clean(value), fmt).date()
        except ValueError:
            continue
    raise RateError(f"Unrecognized official effective date: {value}")


def numbers(line: str) -> list[D]:
    result = []
    for value in NUMBER.findall(line):
        value = value.replace("$", "")
        result.append(-D(value[1:-1]) if value.startswith("(") else D(value))
    return result


def line_values(text: str, pattern: str, count: int | None = None) -> list[D]:
    lines = [line for line in text.splitlines() if re.search(pattern, line, re.I)]
    if len(lines) != 1:
        raise RateError(f"Expected one tariff row matching {pattern!r}; found {len(lines)}")
    values = numbers(lines[0])
    if not values or (count is not None and len(values) != count):
        raise RateError(f"Tariff columns changed for {pattern!r}")
    return values


def document(text: str, url: str, as_of: date, code: str | None = None) -> Document:
    # Ignore serial numbers: PSC 214 is outdoor lighting, not PSC 220.
    psc = re.search(r"P\.?S\.?C\.?\s*(?:NO\s*[:.]?\s*)?[:.]?\s*(\d+)", text, re.I)
    if not psc or psc[1] != "220" or "NIAGARA MOHAWK" not in text.upper():
        raise RateError("Expected a Niagara Mohawk PSC 220 electricity filing")
    if code and not re.search(rf"STATEMENT TYPE\s*:\s*{code}\b", text, re.I):
        raise RateError(f"Expected statement type {code}")
    match = re.search(rf"INITIAL EFFECTIVE(?: DATE)?\s*:\s*({DATE_PATTERN})", text, re.I)
    if not match:
        raise RateError("Tariff effective date is missing")
    effective = parse_date(match[1])
    if effective > as_of:
        raise RateError(f"Tariff is not effective until {effective}")
    return Document(text, url, effective)


def pdf_text(data: bytes, base_only: bool = False) -> str:
    if not data.startswith(b"%PDF"):
        raise RateError("The official source did not return a PDF")
    try:
        reader = PdfReader(BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if base_only:
                if (
                    re.search(r"SERVICE CLASSIFICATION NO\.?\s*1\b", text)
                    and "STANDARD TARIFF CHARGES" in text
                ):
                    return text
            else:
                pages.append(text)
        if not base_only and pages:
            return "\f".join(pages)
    except Exception as err:
        raise RateError("Could not read the official tariff PDF") from err
    raise RateError("The standard SC-1 residential base tariff page is missing")


def index_links(data: bytes) -> dict[str, str]:
    soup = BeautifulSoup(data, "html.parser")
    links = {clean(a.get_text()): urljoin(DPS_ROOT, a["href"]) for a in soup.find_all("a", href=True)}
    if not {"[Leaves]", "[Statements]"} <= links.keys():
        raise RateError("Official tariff index layout changed")
    return links


def named_link(data: bytes, label: str) -> str:
    soup = BeautifulSoup(data, "html.parser")
    links = [
        urljoin(DPS_ROOT, a["href"]) for a in soup.find_all("a", href=True) if clean(a.get_text()) == label
    ]
    if len(links) != 1:
        raise RateError(f"Missing or ambiguous tariff link: {label}")
    return links[0]


def statement_links(data: bytes, as_of: date) -> dict[str, str]:
    soup = BeautifulSoup(data, "html.parser")
    candidates: dict[str, list[tuple[date, str]]] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 7:
            continue
        code = clean(cells[0].get_text())
        if code not in STATEMENTS:
            continue
        effective = parse_date(cells[5].get_text())
        link = row.find("a", href=re.compile("showPDF", re.I))
        if link and effective <= as_of:
            candidates.setdefault(code, []).append((effective, urljoin(DPS_ROOT, link["href"])))
    if missing := STATEMENTS - candidates.keys():
        raise RateError(f"Missing effective PSC 220 statements: {', '.join(sorted(missing))}")
    return {code: max(rows)[1] for code, rows in candidates.items()}


def base_submission_link(data: bytes, as_of: date) -> str:
    soup = BeautifulSoup(data, "html.parser")
    candidates = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 8 or clean(cells[1].get_text()) != "349":
            continue
        effective = parse_date(cells[6].get_text())
        link = row.find("a", href=re.compile("searchSubmissionID", re.I))
        if link and effective <= as_of:
            candidates.append((effective, urljoin(DPS_ROOT, link["href"])))
    if not candidates:
        raise RateError("Effective SC-1 leaf 349 is missing")
    return max(candidates)[1]


def base_pdf_link(data: bytes) -> str:
    soup = BeautifulSoup(data, "html.parser")
    candidates = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2 or clean(cells[0].get_text()) != "220":
            continue
        for link in cells[1].find_all("a", href=True):
            if clean(link.get_text()).lower() == "effective":
                candidates.append(urljoin(DPS_ROOT, link["href"]))
    if len(candidates) != 1:
        raise RateError("Effective PSC 220 leaf PDF is missing or ambiguous")
    return candidates[0]


def base_rates(doc: Document) -> tuple[D, D]:
    if not re.search(r"SERVICE CLASSIFICATION NO\.?\s*1\b", doc.text):
        raise RateError("Expected standard residential SC-1")
    match = re.search(
        r"STANDARD TARIFF CHARGES:.*?Basic Service Charge\s+\$([\d.]+)\s+Per kWh\s+\$([\d.]+)",
        doc.text,
        re.S,
    )
    if not match:
        raise RateError("SC-1 base tariff layout changed")
    return D(match[1]), D(match[2])


def revenue_taxes(doc: Document) -> dict[str, tuple[D, D]]:
    rates = {}
    residential = False
    for page in doc.text.split("\f"):
        if re.search(r"APPLICABLE\s+TO\s+NON[ -]?RESIDENTIAL", page):
            residential = False
        elif re.search(r"APPLICABLE\s+TO\s+RESIDENTIAL", page):
            residential = True
        if not residential:
            continue
        # Rows have two independent municipality/rate pairs across the page.
        for match in re.finditer(
            r"((?:City of|Village of) [A-Za-z .'-]+?|All Other Municipalities)\s+"
            r"(\d+\.\d+)\s+(\d+\.\d+)",
            page,
        ):
            name = clean(match[1])
            values = (D(match[2]) / 100, D(match[3]) / 100)
            if name in rates and rates[name] != values:
                raise RateError("Conflicting residential revenue tax rows")
            rates[name] = values
    if OTHER_MUNICIPALITIES not in rates or len(rates) < 50:
        raise RateError("Residential revenue tax table is incomplete")
    return rates


def municipal_surcharges(doc: Document) -> dict[str, tuple[D, date, date]]:
    # Each filed municipal project has its own start/end dates. These are
    # additional delivery rates, distinct from the revenue tax surcharge.
    pattern = (
        rf"Effective:\s*({DATE_PATTERN})\s+through\s+({DATE_PATTERN})"
        r"\s+Municipality\s+Surcharge\s*\(per kWh\)\s+"
        r"((?:Town|City|Village) of [A-Za-z .'-]+?)\s+\$([\d.]+)"
    )
    matches = list(re.finditer(pattern, doc.text, re.I))
    names = re.findall(r"(?:Town|City|Village) of [A-Za-z .'-]+?(?=\s+\$)", doc.text)
    if not matches or len(matches) != len(names):
        raise RateError("Municipal undergrounding surcharge layout changed")
    return {clean(m[3]): (D(m[4]), parse_date(m[1]), parse_date(m[2])) for m in matches}


def supply_rates(doc: Document, zone: str) -> tuple[D, D, D]:
    # First and third occurrences are SC-1 ESCost and SC-1 ESRM. Validate the
    # six-zone table boundaries so SC-2ND cannot be mistaken for SC-1.
    sections = re.split(r"Rule\s+46\.3\s+Electricity\s+Supply\s+Reconciliation", doc.text)
    if len(sections) != 2:
        raise RateError("Supply reconciliation section changed")
    values = []
    for section in sections:
        start = re.search(r"S\.C\. No\. 1\s", section)
        end = re.search(r"S\.C\. No\. 2ND\s", section)
        if not start or not end or end.start() <= start.start():
            raise RateError("SC-1 supply table boundaries changed")
        rows = section[start.end() : end.start()].splitlines()
        matches = [numbers(row)[-1] for row in rows if re.search(rf"\b{zone}\s*-", row)]
        if len(matches) != 1:
            raise RateError(f"SC-1 supply zone {zone} is missing or ambiguous")
        values.append(matches[0])
    ltc_section = re.split(r"Rule\s+46\.2\.6\.7\s+Residential", doc.text)[0]
    ltc = line_values(ltc_section, r"S\.C\. Nos\. 1 & 1-C")[-1]
    return values[0], values[1], ltc
