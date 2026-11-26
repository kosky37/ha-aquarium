from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
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
        lambda item: [ResetModeButton(item)]
        if isinstance(item, LightItem) and item.control == CONTROL_MODES and item.modes
        else [],
    )


class ResetModeButton(AquariumEntity, ButtonEntity):
    _attr_translation_key = "reset_mode"
    _attr_icon = "mdi:restart"
    _attr_entity_category = EntityCategory.CONFIG
    item: LightItem

    def __init__(self, item: LightItem) -> None:
        super().__init__(item, "reset_mode")

    async def async_press(self) -> None:
        await self.item.async_reset_mode()
