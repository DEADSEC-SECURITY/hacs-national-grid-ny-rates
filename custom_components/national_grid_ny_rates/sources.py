"""Native asynchronous HTTP; PDF parsing runs off Home Assistant's event loop."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import aiohttp

from .const import DPS_INDEX, TAX_URL
from .models import Catalog, RateBook, RateError
from .parsers import (
    base_pdf_link,
    base_submission_link,
    document,
    index_links,
    municipal_surcharges,
    named_link,
    pdf_text,
    revenue_taxes,
    statement_links,
)
from .taxes import parse_sales_taxes


async def _gather(*coroutines):
    """Cancel outstanding document requests if any part of a refresh fails."""
    tasks = [asyncio.ensure_future(coro) for coro in coroutines]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


class NationalGridClient:
    """Retrieve a complete, current public rate book, with immutable PDF caching."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        run_in_executor: Callable[..., Awaitable[Any]] = asyncio.to_thread,
        cache: dict | None = None,
    ) -> None:
        self.session = session
        self.run_in_executor = run_in_executor
        self.cache = cache if cache is not None else {}
        self._semaphore = asyncio.Semaphore(3)
        self._lock = asyncio.Lock()

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"ets.dps.ny.gov", "www.tax.ny.gov"}
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            raise RateError("Unexpected official source URL")

    async def _get(self, url: str, limit: int = 12_000_000) -> bytes:
        self._validate_url(url)
        try:
            async with self._semaphore:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=60),
                    allow_redirects=False,
                ) as response:
                    response.raise_for_status()
                    if response.status != 200:
                        raise RateError(f"Unexpected HTTP status {response.status}")
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        data.extend(chunk)
                        if len(data) > limit:
                            raise RateError("Official document exceeds the supported size")
                    return bytes(data)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RateError(f"Could not retrieve official rates from {urlparse(url).hostname}") from err

    async def _pdf(
        self,
        url: str,
        as_of: date,
        code: str | None = None,
        base_only: bool = False,
        cache_key: str | None = None,
    ):
        self._validate_url(url)
        key = cache_key or url
        cached = self.cache.get(key)
        now = datetime.now(UTC)
        if cached and (
            base_only or now.timestamp() - cached["fetched_at"] < timedelta(days=7).total_seconds()
        ):
            text = cached["text"]
        else:
            data = await self._get(url, limit=65_000_000 if base_only else 12_000_000)
            text = await self.run_in_executor(pdf_text, data, base_only)
            # A bad/future filing must not enter the cache.
            document(text, url, as_of, code)
            self.cache[key] = {"text": text, "fetched_at": now.timestamp()}
            if len(self.cache) > 60:
                oldest = min(self.cache, key=lambda key: self.cache[key]["fetched_at"])
                del self.cache[oldest]
        return document(text, url, as_of, code)

    async def _manifest(self, as_of: date):
        links = await self.run_in_executor(index_links, await self._get(DPS_INDEX))
        urls = await self.run_in_executor(statement_links, await self._get(links["[Statements]"]), as_of)
        return links, urls

    async def async_catalog(self, as_of: date) -> Catalog:
        async with self._lock:
            _, urls = await self._manifest(as_of)
            rts, mun, tax_html = await _gather(
                self._pdf(urls["RTS"], as_of, "RTS"),
                self._pdf(urls["MUN"], as_of, "MUN"),
                self._get(TAX_URL),
            )
            tax = await self.run_in_executor(parse_sales_taxes, tax_html, as_of)
            rts_rows = await self.run_in_executor(revenue_taxes, rts)
            mun_rows = await self.run_in_executor(municipal_surcharges, mun)
            return Catalog(tuple(sorted(set(rts_rows) | set(mun_rows))), tax.jurisdictions)

    async def _base(self, leaves_url: str, as_of: date):
        details_url = await self.run_in_executor(named_link, await self._get(leaves_url), "[Leaves Detail]")
        submission_url = await self.run_in_executor(base_submission_link, await self._get(details_url), as_of)
        url = await self.run_in_executor(base_pdf_link, await self._get(submission_url))
        # DPS's leaf link returns the full tariff book. Key the extracted base
        # page by the effective leaf's submission, so other tariff revisions
        # do not trigger another large download. No PDF binary is persisted.
        return await self._pdf(url, as_of, base_only=True, cache_key="base:" + submission_url)

    async def async_fetch(self, as_of: date) -> RateBook:
        async with self._lock:
            links, urls = await self._manifest(as_of)
            codes = sorted(urls)
            results = await _gather(
                self._base(links["[Leaves]"], as_of),
                self._get(TAX_URL),
                *(self._pdf(urls[code], as_of, code) for code in codes),
            )
            tax = await self.run_in_executor(parse_sales_taxes, results[1], as_of)
            return RateBook(results[0], dict(zip(codes, results[2:], strict=True)), tax, datetime.now(UTC))
