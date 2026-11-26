from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AquariumConfigEntry
from .const import DEVICE_KIND_ICONS
from .controller import DeviceItem, Item, ScheduledItem
from .entity import AquariumEntity, add_per_item
from .schedule import format_value


def _entities(item: Item) -> list[Entity]:
    entities: list[Entity] = []
    if isinstance(item, DeviceItem):
        entities.append(DeviceSwitch(item))
    if isinstance(item, ScheduledItem) and item.points:
        entities.append(ScheduleSwitch(item))
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    add_per_item(entry.runtime_data.items.values(), async_add_entities, _entities)


class DeviceSwitch(AquariumEntity, SwitchEntity):
    _attr_name = None
    item: DeviceItem

    def __init__(self, item: DeviceItem) -> None:
        super().__init__(item, "switch")
        self._attr_icon = DEVICE_KIND_ICONS.get(item.kind or "other", DEVICE_KIND_ICONS["other"])

    @property
    def is_on(self) -> bool:
        return self.item.is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        upcoming = self.item.next_change
        return {
            "target": self.item.target,
            "schedule": self.item.schedule_text,
            "schedule_enabled": self.item.schedule_enabled,
            "next_change": upcoming[0].isoformat() if upcoming else None,
            "next_value": format_value(upcoming[1]) if upcoming else None,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.item.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.item.async_turn_off()


class ScheduleSwitch(AquariumEntity, SwitchEntity, RestoreEntity):
    _attr_translation_key = "schedule"
    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.CONFIG
    item: ScheduledItem

    def __init__(self, item: ScheduledItem) -> None:
        super().__init__(item, "schedule")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.item.schedule_enabled

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None:
            self.item.restore_schedule_enabled(last.state != STATE_OFF)
        await super().async_added_to_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.item.async_set_schedule_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.item.async_set_schedule_enabled(False)
