"""Run the real Home Assistant config flow, entities and coordinator locally."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.national_grid_ny_rates.const import DOMAIN
from custom_components.national_grid_ny_rates.models import RateError

DATA = {"zone": "C", "municipality": "City of Syracuse", "sales_tax_jurisdiction": "__exempt__"}


def entry_for(hass, data=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="National Grid NY Rates",
        data=data or DATA,
        unique_id="C|City of Syracuse|__exempt__",
    )
    entry.add_to_hass(hass)
    return entry


async def test_config_flow_and_duplicate(hass, mock_sources):
    with patch("custom_components.national_grid_ny_rates.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zone": "C"})
        assert result["step_id"] == "location"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {k: v for k, v in DATA.items() if k != "zone"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == DATA
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zone": "C"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {k: v for k, v in DATA.items() if k != "zone"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_exactly_five_sensors_and_energy_price_unit(hass, mock_sources):
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    states = hass.states.async_all("sensor")
    assert len(states) == 5
    expected = {
        "delivery": ".126104",
        "supply": ".07933061775",
        "total_before_tax": ".20543461775",
        "tax": ".00470143786109275",
        "total_including_tax": ".21013605561109275",
    }
    registry = er.async_get(hass)
    for key, value in expected.items():
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
        assert entity_id
        state = hass.states.get(entity_id)
        assert Decimal(state.state) == Decimal(value)
        assert state.attributes["unit_of_measurement"] == "USD/kWh"
        assert state.attributes["state_class"] == "measurement"
        assert state.attributes["sales_tax_percent"] == 0
        assert state.attributes["monthly_service_charge_usd_before_tax"] == 19
        assert state.attributes["effective_dates"]["RTS"] == "2026-06-01"
    assert len(dr.async_get(hass).devices) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_network_failure_marks_all_unavailable_and_recovers(hass, mock_sources):
    fetch, _ = mock_sources
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    fetch.side_effect = RateError("Official tax source unavailable")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert all(state.state == STATE_UNAVAILABLE for state in hass.states.async_all("sensor"))
    fetch.side_effect = None
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert all(state.state != STATE_UNAVAILABLE for state in hass.states.async_all("sensor"))


async def test_first_refresh_failure_retries_setup(hass, mock_sources):
    mock_sources[0].side_effect = RateError("Incomplete rates")
    entry = entry_for(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("sensor")


async def test_reconfigure_same_location_succeeds(hass, mock_sources):
    entry = entry_for(hass)
    with patch("homeassistant.config_entries.ConfigEntries.async_reload", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zone": "C"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {k: v for k, v in DATA.items() if k != "zone"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert entry.unique_id == "C|City of Syracuse|__exempt__"
        await hass.async_block_till_done()


async def test_location_lookup_failure_can_retry(hass, mock_sources):
    mock_sources[1].side_effect = RateError("Source offline")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zone": "C"})
    assert result["errors"] == {"base": "cannot_connect"}
    mock_sources[1].side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert not result["errors"]
    assert "municipality" in str(result["data_schema"].schema)


async def test_six_hour_refresh_updates_tax_automatically(hass, mock_sources, rate_book, freezer):
    data = {
        **DATA,
        "municipality": "City of Schenectady",
        "sales_tax_jurisdiction": "Schenectady School District",
    }
    entry = entry_for(hass, data)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    jurisdictions = dict(rate_book.sales_taxes.jurisdictions)
    jurisdictions["Schenectady School District"] = replace(
        jurisdictions["Schenectady School District"], rate=Decimal(".08")
    )
    mock_sources[0].return_value = replace(
        rate_book, sales_taxes=replace(rate_book.sales_taxes, jurisdictions=jurisdictions)
    )
    freezer.move_to("2026-11-07T23:01:00+00:00")
    async_fire_time_changed(hass, datetime.now(UTC))
    await hass.async_block_till_done()
    assert mock_sources[0].await_count == 2
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_total_including_tax")
    state = hass.states.get(entity_id)
    assert state.attributes["sales_tax_percent"] == 8
    assert Decimal(state.state) == Decimal(".21013605561109275") * Decimal("1.08")


async def test_reconfigure_new_location_keeps_entity_ids(hass, mock_sources):
    entry = entry_for(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids_before = {state.entity_id for state in hass.states.async_all("sensor")}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zone": "F"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "municipality": "City of Albany",
            "sales_tax_jurisdiction": "Albany School District (Albany County)",
        },
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.unique_id == "F|City of Albany|Albany School District (Albany County)"
    assert {state.entity_id for state in hass.states.async_all("sensor")} == ids_before
    assert all(state.attributes["load_zone"] == "F" for state in hass.states.async_all("sensor"))
