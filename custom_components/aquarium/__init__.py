from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .controller import Item, build_item
from .schedule import ScheduleError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class AquariumData:
    items: dict[str, Item] = field(default_factory=dict)


type AquariumConfigEntry = ConfigEntry[AquariumData]


async def async_setup_entry(hass: HomeAssistant, entry: AquariumConfigEntry) -> bool:
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Aquarium",
        model="Aquarium",
    )
    data = AquariumData()
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
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquariumConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: AquariumConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
