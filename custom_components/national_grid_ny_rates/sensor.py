"""Five independent USD/kWh price sensors, including total with taxes."""

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NationalGridConfigEntry
from .const import DOMAIN, NAME
from .coordinator import NationalGridCoordinator

SENSORS = (
    SensorEntityDescription(key="delivery", translation_key="delivery", icon="mdi:transmission-tower"),
    SensorEntityDescription(key="supply", translation_key="supply", icon="mdi:lightning-bolt"),
    SensorEntityDescription(key="total_before_tax", translation_key="total_before_tax", icon="mdi:cash"),
    SensorEntityDescription(key="tax", translation_key="tax", icon="mdi:percent"),
    SensorEntityDescription(
        key="total_including_tax", translation_key="total_including_tax", icon="mdi:cash-check"
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NationalGridConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(NationalGridRateSensor(entry.runtime_data, description) for description in SENSORS)


class NationalGridRateSensor(CoordinatorEntity[NationalGridCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "USD/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 5

    def __init__(self, coordinator: NationalGridCoordinator, description: SensorEntityDescription):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=NAME,
            manufacturer="National Grid / Niagara Mohawk",
            model="SC-1 residential electricity tariff",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://github.com/DEADSEC-SECURITY/national-grid-ny-rates",
        )

    @property
    def native_value(self):
        return self.coordinator.data.value(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.attributes
