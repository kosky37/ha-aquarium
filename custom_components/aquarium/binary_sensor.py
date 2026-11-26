from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AquariumConfigEntry
from .controller import SensorItem
from .entity import AquariumEntity, add_per_item


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    add_per_item(
        entry.runtime_data.items.values(),
        async_add_entities,
        lambda item: [OutOfRange(item)]
        if isinstance(item, SensorItem) and (item.minimum is not None or item.maximum is not None)
        else [],
    )


class OutOfRange(AquariumEntity, BinarySensorEntity):
    _attr_translation_key = "out_of_range"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    item: SensorItem

    def __init__(self, item: SensorItem) -> None:
        super().__init__(item, "out_of_range")

    @property
    def is_on(self) -> bool | None:
        value = self.item.value
        if value is None:
            return None
        low, high = self.item.minimum, self.item.maximum
        return (low is not None and value < low) or (high is not None and value > high)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"min": self.item.minimum, "max": self.item.maximum, "value": self.item.value}
