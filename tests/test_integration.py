from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aquarium.const import DOMAIN

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


LEDDY = {
    "control": "modes",
    "entity_id": "input_boolean.leddy",
    "modes": ["Day", "Daybreak", "Night"],
    "toggle_delay": 0.05,
    "reset_time": 2,
    "schedule": "",
}

FLOW_LEDDY = {**{k: v for k, v in LEDDY.items() if k != "control"}, "toggle_delay": 0.5}


async def _booleans(hass: HomeAssistant, *names: str) -> None:
    await async_setup_component(hass, "input_boolean", {"input_boolean": {name: {} for name in names}})
    await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, *subentries: ConfigSubentryData) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Tank", data={}, subentries_data=list(subentries))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _sub(kind: str, title: str, data: dict) -> ConfigSubentryData:
    return ConfigSubentryData(data=data, subentry_type=kind, title=title, unique_id=None)


async def _toggle(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call(
        "input_boolean", "turn_on" if on else "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_config_flow_and_light_subentry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Tank"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.subentries.async_init((entry.entry_id, "light"), context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Day&Night back", "control": "modes"}
    )
    assert result["step_id"] == "details"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**FLOW_LEDDY, "schedule": "12:00 Day\n20:00 sunset"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"schedule": "invalid_schedule"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {**FLOW_LEDDY, "schedule": "20:00 off\n12:00 day"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Day&Night back"
    assert subentry.data["schedule"] == "12:00 Day\n20:00 off"
    assert subentry.data["modes"] == ["Day", "Daybreak", "Night"]


async def test_mode_cycling(hass: HomeAssistant, monkeypatch) -> None:
    monkeypatch.setattr("custom_components.aquarium.controller.ECHO_GRACE", timedelta(seconds=0.3))
    await _booleans(hass, "leddy")
    await _setup(hass, _sub("light", "Leddy", LEDDY))
    assert hass.states.get("light.leddy").state == "off"

    await hass.services.async_call("light", "turn_on", {"entity_id": "light.leddy", "effect": "Night"}, blocking=True)
    await hass.async_block_till_done()
    state = hass.states.get("light.leddy")
    assert state.state == "on"
    assert state.attributes["effect"] == "Night"
    assert hass.states.get("select.leddy_mode").state == "Night"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.leddy_mode", "option": "Daybreak"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get("light.leddy").attributes["effect"] == "Daybreak"

    hass.states.async_set("input_boolean.leddy", "off")
    hass.states.async_set("input_boolean.leddy", "on")
    await hass.async_block_till_done()
    assert hass.states.get("light.leddy").attributes["effect"] == "Daybreak"

    await asyncio.sleep(0.4)
    await _toggle(hass, "input_boolean.leddy", False)
    await _toggle(hass, "input_boolean.leddy", True)
    assert hass.states.get("light.leddy").attributes["effect"] == "Night"

    await _toggle(hass, "input_boolean.leddy", False)
    await asyncio.sleep(2.1)
    await _toggle(hass, "input_boolean.leddy", True)
    assert hass.states.get("light.leddy").attributes["effect"] == "Day"


async def test_device_schedule_is_reconciled(hass: HomeAssistant, freezer) -> None:
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-11-26 12:30:00+00:00")
    await _booleans(hass, "co2_plug")
    await _setup(
        hass,
        _sub("device", "CO2", {"kind": "co2", "entity_id": "input_boolean.co2_plug", "schedule": "11:00 on\n19:00 off"}),
    )
    assert hass.states.get("input_boolean.co2_plug").state == "on"
    assert hass.states.get("switch.co2").state == "on"
    assert hass.states.get("switch.co2_schedule").state == "on"
    assert hass.states.get("sensor.co2_next_change").attributes["value"] == "off"

    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.co2_schedule"}, blocking=True)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.co2"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.co2_plug").state == "off"

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.co2_schedule"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.co2_plug").state == "on"


async def test_sensor_mirror_and_range(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.water", "24.6", {"unit_of_measurement": "°C"})
    await _setup(
        hass,
        _sub("sensor", "Water", {"kind": "temperature", "entity_id": "sensor.water", "min": 23, "max": 26}),
    )
    assert float(hass.states.get("sensor.water_2").state) == 24.6
    assert hass.states.get("binary_sensor.water_out_of_range").state == "off"
    hass.states.async_set("sensor.water", "27.1", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.water_out_of_range").state == "on"


async def test_adding_and_editing_items_on_a_running_aquarium(hass: HomeAssistant) -> None:
    await _booleans(hass, "filter_plug")
    entry = await _setup(hass)
    result = await hass.config_entries.subentries.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Filter", "kind": "filter", "entity_id": "input_boolean.filter_plug", "schedule": ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("switch.filter").state == "off"
    assert hass.states.get("switch.filter_schedule").state == "on"
    assert hass.states.get("sensor.filter_next_change").state == "unknown"

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.filter"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.filter_plug").state == "on"

    subentry_id = next(iter(entry.subentries))
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Filter", "kind": "filter", "entity_id": "input_boolean.filter_plug", "schedule": "08:00 on\n22:00 off"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert hass.states.get("switch.filter_schedule").state == "on"
    assert entry.subentries[subentry_id].data["schedule"] == "08:00 on\n22:00 off"


async def test_reset_mode_button(hass: HomeAssistant) -> None:
    await _booleans(hass, "leddy")
    await _setup(hass, _sub("light", "Leddy", LEDDY))
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.leddy_mode", "option": "Night"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get("light.leddy").attributes["effect"] == "Night"
    await hass.services.async_call("button", "press", {"entity_id": "button.leddy_reset_mode"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("input_boolean.leddy").state == "on"
    assert hass.states.get("light.leddy").attributes["effect"] == "Day"


async def test_off_then_quick_on_counts_as_a_cycle(hass: HomeAssistant) -> None:
    await _booleans(hass, "leddy")
    await _setup(hass, _sub("light", "Leddy", LEDDY))
    await hass.services.async_call("light", "turn_on", {"entity_id": "light.leddy", "effect": "Daybreak"}, blocking=True)
    await hass.services.async_call("light", "turn_off", {"entity_id": "light.leddy"}, blocking=True)
    await hass.services.async_call("light", "turn_on", {"entity_id": "light.leddy", "effect": "Daybreak"}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("light.leddy").attributes["effect"] == "Daybreak"


async def test_set_schedule_service_updates_in_place(hass: HomeAssistant, monkeypatch) -> None:
    fixed = datetime(2026, 11, 26, 13, 0, tzinfo=UTC)
    monkeypatch.setattr("custom_components.aquarium.controller.local_now", lambda: fixed)
    await _booleans(hass, "leddy")
    entry = await _setup(hass, _sub("light", "Leddy", {**LEDDY, "schedule": "12:00 Daybreak\n20:00 off"}))
    assert hass.states.get("light.leddy").attributes["effect"] == "Daybreak"
    toggles: list[str] = []
    hass.bus.async_listen("state_changed", lambda e: toggles.append(e.data["new_state"].state) if e.data["entity_id"] == "input_boolean.leddy" else None)
    light_entity = hass.states.get("light.leddy")

    await hass.services.async_call(
        "aquarium",
        "set_schedule",
        {"entity_id": "light.leddy", "schedule": [{"at": "21:00", "value": "off"}, {"at": "11:00", "value": "daybreak"}]},
        blocking=True,
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["schedule"] == "11:00 Daybreak\n21:00 off"
    state = hass.states.get("light.leddy")
    assert state.attributes["schedule_points"] == [{"at": "11:00", "value": "Daybreak"}, {"at": "21:00", "value": "off"}]
    assert state.attributes["effect"] == "Daybreak"
    assert state.context is not None and light_entity is not None
    assert toggles == []

    with pytest.raises(Exception, match="line 1"):
        await hass.services.async_call(
            "aquarium", "set_schedule", {"entity_id": "light.leddy", "schedule": "13:00 sunset"}, blocking=True
        )

    await hass.services.async_call(
        "aquarium", "set_schedule", {"entity_id": "light.leddy", "schedule": "12:00 Night\n21:00 off"}, blocking=True
    )
    await hass.async_block_till_done()
    await asyncio.sleep(0.3)
    await hass.async_block_till_done()
    assert hass.states.get("light.leddy").attributes["effect"] == "Night"
    assert toggles == ["off", "on"]
