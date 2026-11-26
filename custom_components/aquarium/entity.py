from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SUBENTRY_DEVICE, SUBENTRY_LIGHT, SUBENTRY_SENSOR
from .controller import Item

MODEL_NAMES = {
    SUBENTRY_LIGHT: "Light",
    SUBENTRY_DEVICE: "Device",
    SUBENTRY_SENSOR: "Sensor",
}

KIND_LABELS = {
    "co2": "CO2",
    "filter": "Filter",
    "heater": "Heater",
    "pump": "Pump",
    "air_pump": "Air pump",
    "uv": "UV sterilizer",
    "feeder": "Feeder",
    "other": "Device",
    "temperature": "Temperature sensor",
    "ph": "pH sensor",
    "tds": "TDS sensor",
    "conductivity": "Conductivity sensor",
    "oxygen": "Oxygen sensor",
}


class AquariumEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, item: Item, key: str) -> None:
        self.item = item
        self._attr_unique_id = f"{item.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, item.subentry_id)},
            name=item.name,
            manufacturer="Aquarium",
            model=KIND_LABELS.get(item.kind or "", MODEL_NAMES.get(item.subentry.subentry_type, "Item")),
            via_device=(DOMAIN, item.entry.entry_id),
        )

    @property
    def available(self) -> bool:
        return self.item.available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.item.add_listener(self.async_write_ha_state))


def add_per_item(
    items: Iterable[Item],
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[Item], list[Entity]],
) -> None:
    for item in items:
        entities = factory(item)
        if entities:
            async_add_entities(entities, config_subentry_id=item.subentry_id)
