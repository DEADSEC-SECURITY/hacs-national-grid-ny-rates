"""Location selection: select jurisdictions, never maintain percentages."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_MUNICIPALITY,
    CONF_SALES_TAX,
    CONF_ZONE,
    DOMAIN,
    EXEMPT_JURISDICTION,
    NAME,
    OTHER_MUNICIPALITIES,
    ZONES,
)
from .coordinator import async_get_client, today
from .models import RateError
from .rates import calculate

LOGGER = logging.getLogger(__name__)


class NationalGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._zone = None
        self._catalog = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_ZONE) in ZONES:
                self._zone = user_input[CONF_ZONE]
                return await self.async_step_location()
            errors[CONF_ZONE] = "invalid_zone"
        default = (
            self._get_reconfigure_entry().data[CONF_ZONE] if self.source == "reconfigure" else vol.UNDEFINED
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZONE, default=default): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[{"value": key, "label": label} for key, label in ZONES.items()],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_location(self, user_input=None):
        errors = {}
        try:
            client = await async_get_client(self.hass)
            if self._catalog is None:
                self._catalog = await client.async_catalog(today())
        except RateError as err:
            LOGGER.warning("Could not load official tax locations: %s", err)
            return self.async_show_form(
                step_id="location", data_schema=vol.Schema({}), errors={"base": "cannot_connect"}
            )

        if user_input:
            municipality = user_input.get(CONF_MUNICIPALITY)
            jurisdiction = user_input.get(CONF_SALES_TAX)
            if (
                municipality not in self._catalog.municipalities
                or jurisdiction not in self._catalog.sales_taxes
            ):
                errors["base"] = "invalid_location"
            else:
                data = {CONF_ZONE: self._zone, CONF_MUNICIPALITY: municipality, CONF_SALES_TAX: jurisdiction}
                try:
                    book = await client.async_fetch(today())
                    await self.hass.async_add_executor_job(
                        calculate, book, self._zone, municipality, jurisdiction, today()
                    )
                except RateError as err:
                    LOGGER.warning("Could not validate complete residential rate: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    unique_id = "|".join((self._zone, municipality, jurisdiction))
                    if self.source == "reconfigure":
                        entry = self._get_reconfigure_entry()
                        existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                            DOMAIN, unique_id
                        )
                        if existing and existing.entry_id != entry.entry_id:
                            return self.async_abort(reason="already_configured")
                        return self.async_update_reload_and_abort(
                            entry, data_updates=data, unique_id=unique_id
                        )
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=NAME, data=data)

        defaults = self._get_reconfigure_entry().data if self.source == "reconfigure" else {}
        municipalities = [
            {
                "value": name,
                "label": (
                    "Outside all listed cities/villages (and listed undergrounding areas)"
                    if name == OTHER_MUNICIPALITIES
                    else name
                ),
            }
            for name in self._catalog.municipalities
        ]
        sales_options = [
            {
                "value": key,
                "label": value.label
                + (f" — temporary exemption through {value.expires}" if value.expires else ""),
            }
            for key, value in self._catalog.sales_taxes.items()
        ]
        sales_options.sort(key=lambda option: (option["value"] == EXEMPT_JURISDICTION, option["label"]))
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MUNICIPALITY, default=defaults.get(CONF_MUNICIPALITY, vol.UNDEFINED)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=municipalities, mode=selector.SelectSelectorMode.DROPDOWN
                        ),
                    ),
                    vol.Required(
                        CONF_SALES_TAX, default=defaults.get(CONF_SALES_TAX, vol.UNDEFINED)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sales_options, mode=selector.SelectSelectorMode.DROPDOWN
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        return await self.async_step_user(user_input)
