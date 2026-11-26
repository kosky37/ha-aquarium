from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariumConfigEntry
from .const import SENSOR_KIND_ICONS
from .controller import Item, ScheduledItem, SensorItem
from .entity import AquariumEntity, add_per_item
from .schedule import format_value

KIND_DEVICE_CLASSES = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "ph": SensorDeviceClass.PH,
    "conductivity": SensorDeviceClass.CONDUCTIVITY,
}


def _entities(item: Item) -> list[Entity]:
    if isinstance(item, SensorItem):
        return [MirrorSensor(item)]
    if isinstance(item, ScheduledItem) and item.points:
        return [NextChangeSensor(item)]
    return []


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    add_per_item(entry.runtime_data.items.values(), async_add_entities, _entities)


class MirrorSensor(AquariumEntity, SensorEntity):
    _attr_name = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    item: SensorItem

    def __init__(self, item: SensorItem) -> None:
        super().__init__(item, "value")
        kind = item.kind or "other"
        self._attr_icon = SENSOR_KIND_ICONS.get(kind, SENSOR_KIND_ICONS["other"])
        self._attr_device_class = KIND_DEVICE_CLASSES.get(kind)

    @property
    def native_value(self) -> float | None:
        return self.item.value

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._attr_device_class == SensorDeviceClass.PH:
            return None
        state = self.item.target_state
        return state.attributes.get("unit_of_measurement") if state else None

    @property
    def suggested_display_precision(self) -> int | None:
        return 2 if self._attr_device_class == SensorDeviceClass.PH else 1

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source": self.item.target, "min": self.item.minimum, "max": self.item.maximum}


class NextChangeSensor(AquariumEntity, SensorEntity):
    _attr_translation_key = "next_change"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"
    item: ScheduledItem

    def __init__(self, item: ScheduledItem) -> None:
        super().__init__(item, "next_change")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> datetime | None:
        upcoming = self.item.next_change
        return upcoming[0] if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        upcoming = self.item.next_change
        return {"value": format_value(upcoming[1]) if upcoming else None}
