from datetime import date
from decimal import Decimal as D

import pytest

from custom_components.national_grid_ny_rates.models import RateError
from custom_components.national_grid_ny_rates.taxes import parse_sales_taxes, percentage, selected_sales_tax

from .conftest import AS_OF, FIXTURES


@pytest.mark.parametrize(
    ("text", "expected"), [("4¾", ".0475"), ("7¾", ".0775"), ("2½", ".025"), ("3", ".03")]
)
def test_fractional_rates(text, expected):
    assert percentage(text) == D(expected)


def test_combined_school_district_rates_are_not_added_again(rate_book):
    taxes = rate_book.sales_taxes
    assert taxes.jurisdictions["Lackawanna School District"].rate == D(".0775")
    assert taxes.jurisdictions["Schenectady School District"].rate == D(".07")
    assert taxes.jurisdictions["Niagara Falls School District"].rate == D(".07")
    # Heating fuel Part 2 has different rows; it is never merged into Part 1.
    assert "Ogdensburg (city)" not in taxes.jurisdictions


def test_temporary_exemption_expiration(rate_book):
    taxes = rate_book.sales_taxes
    selected = selected_sales_tax(taxes, "Chemung County", date(2026, 11, 30))
    assert selected.rate == 0
    assert selected.expires == date(2026, 11, 30)
    with pytest.raises(RateError, match="expired"):
        selected_sales_tax(taxes, "Chemung County", date(2026, 12, 1))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.replace(b"Part 1", b"Part X"),
        lambda b: b.replace(b"4&#190;", b"unknown"),
        lambda b: b.replace(b"Effective June 1, 2026", b"Effective June 1, 2027"),
        lambda b: b.replace(b"continuing through", b"exempt through"),
    ],
)
def test_changed_or_future_publication_fails(mutation):
    raw = (FIXTURES / "pub718r.html").read_bytes()
    changed = mutation(raw)
    assert changed != raw
    with pytest.raises(RateError):
        parse_sales_taxes(changed, AS_OF)


@pytest.mark.parametrize("bad", ["", "NaN", "-4", "100", "4x"])
def test_bad_percentage_fails(bad):
    with pytest.raises(RateError):
        percentage(bad)
