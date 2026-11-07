"""Account-free National Grid upstate New York electricity rates."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import NationalGridCoordinator, async_get_client

PLATFORMS = [Platform.SENSOR]
type NationalGridConfigEntry = ConfigEntry[NationalGridCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NationalGridConfigEntry) -> bool:
    client = await async_get_client(hass)
    coordinator = NationalGridCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NationalGridConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
