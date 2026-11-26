from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariumConfigEntry
from .const import CONTROL_MODES
from .controller import LightItem
from .entity import AquariumEntity, add_per_item


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    add_per_item(
        entry.runtime_data.items.values(),
        async_add_entities,
        lambda item: [ModeSelect(item)]
        if isinstance(item, LightItem) and item.control == CONTROL_MODES and item.modes
        else [],
    )


class ModeSelect(AquariumEntity, SelectEntity):
    _attr_translation_key = "mode"
    _attr_icon = "mdi:theme-light-dark"
    item: LightItem

    def __init__(self, item: LightItem) -> None:
        super().__init__(item, "mode")
        self._attr_options = list(item.modes)

    @property
    def current_option(self) -> str | None:
        return self.item.mode

    async def async_select_option(self, option: str) -> None:
        await self.item.async_turn_on(mode=option)
