"""Fetch all components together and mark incomplete prices unavailable."""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MUNICIPALITY, CONF_SALES_TAX, CONF_ZONE, DOMAIN, NAME
from .models import RateError, RateResult
from .rates import calculate
from .sources import NationalGridClient

LOGGER = logging.getLogger(__name__)
NEW_YORK = ZoneInfo("America/New_York")


def today():
    return datetime.now(NEW_YORK).date()


async def async_get_client(hass: HomeAssistant) -> NationalGridClient:
    shared = hass.data.setdefault(DOMAIN, {})
    if "lock" not in shared:
        shared["lock"] = asyncio.Lock()
    async with shared["lock"]:
        if "client" not in shared:
            store = Store(hass, 1, f"{DOMAIN}.public_pdf_cache")
            cached = await store.async_load()
            cache = {}
            if isinstance(cached, dict):
                cache = {
                    k: v
                    for k, v in cached.items()
                    if isinstance(v, dict)
                    and isinstance(v.get("text"), str)
                    and isinstance(v.get("fetched_at"), (int, float))
                }
            shared["store"] = store
            shared["client"] = NationalGridClient(
                async_get_clientsession(hass),
                hass.async_add_executor_job,
                cache,
            )
    return shared["client"]


class NationalGridCoordinator(DataUpdateCoordinator[RateResult]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: NationalGridClient):
        super().__init__(
            hass,
            LOGGER,
            name=NAME,
            config_entry=entry,
            update_interval=timedelta(hours=6),
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> RateResult:
        as_of = today()
        try:
            book = await self.client.async_fetch(as_of)
            result = await self.hass.async_add_executor_job(
                calculate,
                book,
                self.entry.data[CONF_ZONE],
                self.entry.data[CONF_MUNICIPALITY],
                self.entry.data[CONF_SALES_TAX],
                as_of,
            )
        except RateError as err:
            raise UpdateFailed(str(err)) from err
        try:
            await self.hass.data[DOMAIN]["store"].async_save(self.client.cache)
        except OSError:
            LOGGER.warning("Could not save the public tariff PDF cache")
        return result
