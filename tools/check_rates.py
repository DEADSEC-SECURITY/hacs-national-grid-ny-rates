#!/usr/bin/env python3
"""Exercise exactly the integration's source retrieval and price calculation."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.national_grid_ny_rates.rates import calculate, catalog  # noqa: E402
from custom_components.national_grid_ny_rates.sources import NationalGridClient  # noqa: E402


async def main(args):
    as_of = datetime.now(ZoneInfo("America/New_York")).date()
    async with aiohttp.ClientSession() as session:
        client = NationalGridClient(session)
        book = await client.async_fetch(as_of)
        result = calculate(book, args.zone, args.municipality, args.sales_tax, as_of)
        report = {
            "as_of": as_of.isoformat(),
            "unit": "USD/kWh",
            "entities": {
                name: str(result.value(name))
                for name in (
                    "delivery",
                    "supply",
                    "total_before_tax",
                    "tax",
                    "total_including_tax",
                )
            },
            "attributes": result.attributes,
            "public_rate_catalog": {
                "municipalities": len(catalog(book).municipalities),
                "sales_tax_options": len(book.sales_taxes.jurisdictions),
            },
            "home_assistant_installed_or_changed": False,
        }
        text = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n")
        print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", choices=list("ABCDEF"), required=True)
    parser.add_argument("--municipality", required=True)
    parser.add_argument(
        "--sales-tax",
        required=True,
        help="Exact Publication 718-R Part 1 name, or __exempt__ if none applies",
    )
    parser.add_argument("--output", type=Path)
    asyncio.run(main(parser.parse_args()))
