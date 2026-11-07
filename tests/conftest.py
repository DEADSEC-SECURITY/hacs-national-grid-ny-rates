"""Public fixtures and a real, isolated Home Assistant test runtime."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.national_grid_ny_rates.const import STATEMENTS
from custom_components.national_grid_ny_rates.models import RateBook
from custom_components.national_grid_ny_rates.parsers import document, pdf_text
from custom_components.national_grid_ny_rates.rates import catalog
from custom_components.national_grid_ny_rates.taxes import parse_sales_taxes

FIXTURES = Path(__file__).parent / "fixtures" / "public"
AS_OF = date(2026, 11, 7)


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def frozen_date(freezer):
    freezer.move_to("2026-11-07T17:00:00+00:00")


@pytest.fixture(scope="session")
def rate_book():
    sources = json.loads((FIXTURES / "sources.json").read_text())["files"]
    docs = {
        code: document(
            pdf_text((FIXTURES / f"{code.lower()}.pdf").read_bytes()),
            sources[f"{code.lower()}.pdf"]["url"],
            AS_OF,
            code,
        )
        for code in STATEMENTS
    }
    base = document(
        pdf_text((FIXTURES / "base.pdf").read_bytes(), True),
        "https://ets.dps.ny.gov/ets_web/search/showPDF.cfm?public-base-fixture",
        AS_OF,
    )
    taxes = parse_sales_taxes((FIXTURES / "pub718r.html").read_bytes(), AS_OF)
    return RateBook(base, docs, taxes, datetime(2026, 11, 7, 17, tzinfo=UTC))


@pytest.fixture
def mock_sources(rate_book):
    with (
        patch(
            "custom_components.national_grid_ny_rates.sources.NationalGridClient.async_fetch",
            return_value=rate_book,
        ) as fetch,
        patch(
            "custom_components.national_grid_ny_rates.sources.NationalGridClient.async_catalog",
            return_value=catalog(rate_book),
        ) as locations,
    ):
        yield fetch, locations
