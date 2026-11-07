"""Home Assistant independent data and calculation types."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


class RateError(ValueError):
    """An official source is missing, ambiguous, unsupported or not applicable."""


@dataclass(frozen=True)
class Document:
    text: str
    url: str
    effective: date


@dataclass(frozen=True)
class SalesTax:
    label: str
    rate: Decimal
    expires: date | None = None


@dataclass(frozen=True)
class TaxTable:
    effective: date
    jurisdictions: dict[str, SalesTax]


@dataclass(frozen=True)
class Catalog:
    municipalities: tuple[str, ...]
    sales_taxes: dict[str, SalesTax]


@dataclass(frozen=True)
class RateResult:
    delivery: Decimal
    supply: Decimal
    total_before_tax: Decimal
    tax: Decimal
    total_including_tax: Decimal
    attributes: dict

    def value(self, key: str) -> Decimal:
        return getattr(self, key)


@dataclass(frozen=True)
class RateBook:
    base: Document
    statements: dict[str, Document]
    sales_taxes: TaxTable
    fetched_at: datetime
