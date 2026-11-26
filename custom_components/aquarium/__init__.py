from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import CONF_SCHEDULE, DOMAIN
from .controller import Item, ScheduledItem, build_item
from .schedule import ScheduleError, format_schedule, format_value

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SET_SCHEDULE = "set_schedule"
CARD_URL = "/aquarium/aquarium-card.js"

_POINT = vol.Schema({vol.Required("at"): cv.string, vol.Required("value"): vol.Any(int, cv.string)})
SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("schedule"): vol.Any(cv.string, [_POINT], []),
    }
)


@dataclass
class AquariumData:
    items: dict[str, Item] = field(default_factory=dict)
    snapshot: dict[str, dict[str, Any]] = field(default_factory=dict)


type AquariumConfigEntry = ConfigEntry[AquariumData]


def _snapshot(entry: ConfigEntry) -> dict[str, dict[str, Any]]:
    return {
        subentry_id: {"title": subentry.title, **subentry.data}
        for subentry_id, subentry in entry.subentries.items()
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await _async_register_card(hass)

    async def set_schedule(call: ServiceCall) -> None:
        await _async_set_schedule(hass, call.data["entity_id"], call.data["schedule"])

    hass.services.async_register(DOMAIN, SERVICE_SET_SCHEDULE, set_schedule, schema=SET_SCHEDULE_SCHEMA)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    if getattr(hass, "http", None) is None:
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    integration = await async_get_integration(hass, DOMAIN)
    path = Path(__file__).parent / "frontend" / "aquarium-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), False)])
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")


def _find_item(hass: HomeAssistant, entity_id: str) -> tuple[AquariumConfigEntry, ConfigSubentry, ScheduledItem]:
    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry is None or registry_entry.platform != DOMAIN or registry_entry.config_entry_id is None:
        raise ServiceValidationError(f"{entity_id} is not an aquarium light or device")
    entry = hass.config_entries.async_get_entry(registry_entry.config_entry_id)
    if entry is None or not hasattr(entry, "runtime_data"):
        raise ServiceValidationError(f"The aquarium of {entity_id} is not loaded")
    subentry_id = registry_entry.config_subentry_id
    item = entry.runtime_data.items.get(subentry_id or "")
    if not isinstance(item, ScheduledItem) or subentry_id not in entry.subentries:
        raise ServiceValidationError(f"{entity_id} has no schedule")
    return entry, entry.subentries[subentry_id], item


async def _async_set_schedule(hass: HomeAssistant, entity_id: str, schedule: str | list[dict[str, Any]]) -> None:
    entry, subentry, item = _find_item(hass, entity_id)
    if isinstance(schedule, list):
        text = "\n".join(f"{point['at']} {format_value(point['value'])}" for point in schedule)
    else:
        text = schedule
    try:
        normalized = format_schedule(item.parse(text))
    except ScheduleError as err:
        raise ServiceValidationError(f"Schedule line {err.line}: {err.reason}") from err
    hass.config_entries.async_update_subentry(entry, subentry, data={**subentry.data, CONF_SCHEDULE: normalized})


async def async_setup_entry(hass: HomeAssistant, entry: AquariumConfigEntry) -> bool:
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Aquarium",
        model="Aquarium",
    )
    data = AquariumData(snapshot=_snapshot(entry))
    for subentry in entry.subentries.values():
        try:
            data.items[subentry.subentry_id] = build_item(hass, entry, subentry)
        except ScheduleError as err:
            _LOGGER.error("%s: invalid schedule, %s", subentry.title, err)
    entry.runtime_data = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for item in data.items.values():
        item.async_start()
        entry.async_on_unload(item.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquariumConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_entry_updated(hass: HomeAssistant, entry: AquariumConfigEntry) -> None:
    if not _async_update_in_place(entry):
        await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_update_in_place(entry: AquariumConfigEntry) -> bool:
    data = entry.runtime_data
    new = _snapshot(entry)
    old = data.snapshot
    if new.keys() != old.keys():
        return False
    changed: dict[str, str] = {}
    for subentry_id, values in new.items():
        before = old[subentry_id]
        if {k: v for k, v in values.items() if k != CONF_SCHEDULE} != {
            k: v for k, v in before.items() if k != CONF_SCHEDULE
        }:
            return False
        if values.get(CONF_SCHEDULE) != before.get(CONF_SCHEDULE):
            item = data.items.get(subentry_id)
            if not isinstance(item, ScheduledItem):
                return False
            changed[subentry_id] = values.get(CONF_SCHEDULE) or ""
    for subentry_id, text in changed.items():
        item = data.items[subentry_id]
        if isinstance(item, ScheduledItem):
            item.async_update_schedule(text)
    data.snapshot = new
    return True
