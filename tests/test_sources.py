"""Real PDF extraction and complete retrieval using captured public responses."""

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.national_grid_ny_rates.const import DPS_INDEX, STATEMENTS, TAX_URL
from custom_components.national_grid_ny_rates.models import RateError
from custom_components.national_grid_ny_rates.parsers import (
    base_pdf_link,
    base_submission_link,
    document,
    index_links,
    named_link,
    pdf_text,
    statement_links,
)
from custom_components.national_grid_ny_rates.sources import NationalGridClient, _gather

from .conftest import AS_OF, FIXTURES


def public_responses():
    index = (FIXTURES / "index.html").read_bytes()
    leaves = (FIXTURES / "leaves.html").read_bytes()
    details = (FIXTURES / "leaves-detail.html").read_bytes()
    submission = (FIXTURES / "base-submission.html").read_bytes()
    statements = (FIXTURES / "statements.html").read_bytes()
    links = index_links(index)
    urls = statement_links(statements, AS_OF)
    responses = {
        DPS_INDEX: index,
        links["[Statements]"]: statements,
        links["[Leaves]"]: leaves,
        named_link(leaves, "[Leaves Detail]"): details,
        base_submission_link(details, AS_OF): submission,
        base_pdf_link(submission): (FIXTURES / "base.pdf").read_bytes(),
        TAX_URL: (FIXTURES / "pub718r.html").read_bytes(),
    }
    responses.update({url: (FIXTURES / f"{code.lower()}.pdf").read_bytes() for code, url in urls.items()})
    return responses


async def test_complete_native_client_and_pdf_cache():
    responses = public_responses()
    client = NationalGridClient(MagicMock())

    async def get(url, **kwargs):
        return responses[url]

    client._get = AsyncMock(side_effect=get)
    book = await client.async_fetch(AS_OF)
    assert book.statements.keys() == STATEMENTS
    assert book.base.effective == date(2026, 4, 1)
    assert len(book.sales_taxes.jurisdictions) == 56
    assert len(client.cache) == 14
    calls = client._get.await_count
    await client.async_fetch(AS_OF)
    # Six index/HTML requests remain live. All 14 PDF extractions are cached.
    assert client._get.await_count - calls == 6
    assert len((await client.async_catalog(AS_OF)).municipalities) == 148


async def test_missing_current_adjustment_stops_complete_fetch():
    raw = (FIXTURES / "statements.html").read_bytes().replace(b">RDM&", b">BAD&")
    assert raw != (FIXTURES / "statements.html").read_bytes()
    with pytest.raises(RateError, match="Missing effective"):
        statement_links(raw, AS_OF)


@pytest.mark.parametrize(
    "url",
    [
        "http://ets.dps.ny.gov/rates",
        "https://example.com/rates",
        "https://www.tax.ny.gov.evil.example/",
        "https://person:password@www.tax.ny.gov/",
        "https://ets.dps.ny.gov:444/",
    ],
)
async def test_unexpected_source_urls_are_rejected(url):
    client = NationalGridClient(MagicMock())
    with pytest.raises(RateError, match="Unexpected official source"):
        await client._get(url)


def test_wrong_tariff_and_future_document_rejected(rate_book):
    text = rate_book.statements["RTS"].text
    with pytest.raises(RateError, match="PSC 220"):
        document(text.replace("220", "214"), "url", AS_OF, "RTS")
    with pytest.raises(RateError, match="not effective"):
        document(text, "url", date(2026, 5, 31), "RTS")
    with pytest.raises(RateError, match="statement type"):
        document(text, "url", AS_OF, "RDM")
    with pytest.raises(RateError, match="did not return a PDF"):
        pdf_text(b"<html>challenge</html>")


def test_incomplete_residential_rts_fails(rate_book):
    from dataclasses import replace

    from custom_components.national_grid_ny_rates.parsers import revenue_taxes

    bad = replace(
        rate_book.statements["RTS"], text="APPLICABLE TO RESIDENTIAL\nCity of Syracuse 1.01010 3.09278"
    )
    with pytest.raises(RateError, match="incomplete"):
        revenue_taxes(bad)


def test_residential_continuation_page_without_repeated_heading():
    from custom_components.national_grid_ny_rates.parsers import revenue_taxes

    doc = document(
        pdf_text((FIXTURES / "rts5.pdf").read_bytes()),
        "https://www.nationalgridus.com/media/pdfs/billing-payments/electric-rates/upstate-ny/staterts5.pdf",
        AS_OF,
        "RTS",
    )
    rates = revenue_taxes(doc)
    assert rates["All Other Municipalities"][1] == Decimal(".0204082")
    assert rates["City of Syracuse"][1] == Decimal(".0309278")


async def test_redirect_is_not_followed():
    session = MagicMock()
    response = MagicMock()
    session.get.return_value.__aenter__.return_value = response
    response.status = 302
    client = NationalGridClient(session)
    with pytest.raises(RateError, match="HTTP status 302"):
        await client._get(TAX_URL)
    assert session.get.call_args.kwargs["allow_redirects"] is False


async def test_failed_refresh_cancels_outstanding_requests():
    cancelled = asyncio.Event()

    async def pending():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def failed():
        await asyncio.sleep(0)
        raise RateError("Missing official source")

    with pytest.raises(RateError):
        await _gather(pending(), failed())
    assert cancelled.is_set()
