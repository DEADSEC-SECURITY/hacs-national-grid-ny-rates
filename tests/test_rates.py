"""Independent rate facts and tax arithmetic across the supported territory."""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from custom_components.national_grid_ny_rates.models import RateError
from custom_components.national_grid_ny_rates.parsers import base_rates, revenue_taxes, supply_rates
from custom_components.national_grid_ny_rates.rates import calculate, catalog

TODAY = date(2026, 11, 7)


def test_syracuse_matches_independently_checked_prototype(rate_book):
    result = calculate(rate_book, "C", "City of Syracuse", "__exempt__", TODAY)
    assert result.delivery == D(".126104")
    assert result.supply == D(".07933061775")
    assert result.total_before_tax == D(".20543461775")
    assert result.tax == D(".00470143786109275")
    assert result.total_including_tax == D(".21013605561109275")
    assert result.attributes["monthly_service_charge_usd_before_tax"] == 19
    assert result.attributes["fixed_charge_included_in_kwh_price"] is False
    assert base_rates(rate_book.base) == (D("19"), D(".10013"))


@pytest.mark.parametrize(
    ("zone", "esc", "esrm"),
    [
        ("A", ".06291", ".000910"),
        ("B", ".06498", ".003998"),
        ("C", ".06674", ".003421"),
        ("D", ".06604", ".006180"),
        ("E", ".06863", ".003438"),
        ("F", ".07009", ".010410"),
    ],
)
def test_all_six_sc1_supply_zones(rate_book, zone, esc, esrm):
    # Facts from SC-184, not derived from the implementation under test.
    assert supply_rates(rate_book.statements["SC"], zone) == (D(esc), D(esrm), D("-.000548"))
    result = calculate(rate_book, zone, "City of Syracuse", "__exempt__", TODAY)
    expected_mfc = (
        (D(esc) + D(esrm) + D(".00668")) * D(".0229") + (D(esc) + D(esrm)) * D(".00285") + D(".00053")
    )
    assert result.supply == D(esc) + D(esrm) + D(".00668") + expected_mfc


@pytest.mark.parametrize(
    ("place", "jurisdiction", "supply_tax", "delivery_tax", "sales_tax", "mun"),
    [
        ("City of Syracuse", "__exempt__", ".010101", ".0309278", "0", "0"),
        ("City of Buffalo", "Erie County (outside the following)", ".0309278", ".0526316", ".0475", "0"),
        ("City of Schenectady", "Schenectady School District", ".010101", ".0309278", ".07", "0"),
        ("City of Albany", "Albany School District (Albany County)", ".010101", ".0309278", ".03", "0"),
        ("City of Oswego", "Oswego (city) (Oswego County)", ".010101", ".0309278", ".04", "0"),
        ("All Other Municipalities", "__exempt__", "0", ".0204082", "0", "0"),
        (
            "Village of Clayton",
            "Watertown School District (Jefferson County)",
            ".010101",
            ".0309278",
            ".03",
            ".015494",
        ),
        ("Town of Queensbury", "__exempt__", "0", ".0204082", "0", ".001075"),
    ],
)
def test_tax_rules_and_municipal_surcharges(
    rate_book, place, jurisdiction, supply_tax, delivery_tax, sales_tax, mun
):
    # These are arithmetic scenarios, not a claim that every school district
    # overlaps every municipality used here.
    result = calculate(rate_book, "C", place, jurisdiction, TODAY)
    supply = D(".07933061775")
    delivery = D(".126104") + D(mun)
    expected = (supply * (1 + D(supply_tax)) + delivery * (1 + D(delivery_tax))) * (1 + D(sales_tax))
    assert result.total_including_tax == expected
    assert result.tax == expected - supply - delivery


def test_all_municipalities_and_tax_jurisdictions_are_calculable(rate_book):
    places = catalog(rate_book)
    assert len(places.municipalities) == 148
    assert len(places.sales_taxes) == 56
    for zone in "ABCDEF":
        for municipality in places.municipalities:
            result = calculate(rate_book, zone, municipality, "__exempt__", TODAY)
            assert result.total_including_tax == result.total_before_tax + result.tax
        for jurisdiction in places.sales_taxes:
            result = calculate(rate_book, zone, "All Other Municipalities", jurisdiction, TODAY)
            assert result.total_including_tax > result.total_before_tax


def test_revenue_table_only_uses_residential_pages(rate_book):
    rates = revenue_taxes(rate_book.statements["RTS"])
    assert len(rates) == 147
    assert rates["City of Syracuse"] == (D(".010101"), D(".0309278"))
    assert rates["City of Buffalo"] == (D(".0309278"), D(".0526316"))
    assert rates["Village of East Syracuse"] == rates["Village of North Syracuse"]


@pytest.mark.parametrize(
    ("zone", "place", "jurisdiction"),
    [
        ("UK", "City of Syracuse", "__exempt__"),
        ("C", "Syracuse", "__exempt__"),
        ("C", "City of Syracuse", "not a real jurisdiction"),
    ],
)
def test_unknown_locations_fail_instead_of_zero_tax(rate_book, zone, place, jurisdiction):
    with pytest.raises(RateError):
        calculate(rate_book, zone, place, jurisdiction, TODAY)


def test_future_filing_fails(rate_book):
    statements = dict(rate_book.statements)
    statements["RDM"] = replace(statements["RDM"], effective=date(2027, 1, 1))
    with pytest.raises(RateError, match="not yet effective"):
        calculate(replace(rate_book, statements=statements), "C", "City of Syracuse", "__exempt__", TODAY)


def test_missing_adjustment_row_fails(rate_book):
    statements = dict(rate_book.statements)
    statements["RDM"] = replace(statements["RDM"], text="Missing SC-1 row")
    with pytest.raises(RateError, match="Expected one tariff row"):
        calculate(replace(rate_book, statements=statements), "C", "City of Syracuse", "__exempt__", TODAY)


def test_undergrounding_expiry(rate_book):
    before = calculate(rate_book, "C", "Town of Queensbury", "__exempt__", date(2027, 3, 30))
    after = calculate(rate_book, "C", "Town of Queensbury", "__exempt__", date(2027, 3, 31))
    assert before.delivery - after.delivery == D(".001075")
