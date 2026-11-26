from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AquariumConfigEntry
from .const import CONTROL_DIMMABLE, CONTROL_MODES, LIGHT_ICON
from .controller import LightItem
from .entity import AquariumEntity, add_per_item
from .schedule import format_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    add_per_item(
        entry.runtime_data.items.values(),
        async_add_entities,
        lambda item: [AquariumLight(item)] if isinstance(item, LightItem) else [],
    )


class AquariumLight(AquariumEntity, LightEntity, RestoreEntity):
    _attr_name = None
    _attr_icon = LIGHT_ICON
    item: LightItem

    def __init__(self, item: LightItem) -> None:
        super().__init__(item, "light")
        if item.control == CONTROL_DIMMABLE:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_supported_features = LightEntityFeature.TRANSITION
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        if item.control == CONTROL_MODES:
            self._attr_supported_features = LightEntityFeature.EFFECT
            self._attr_effect_list = list(item.modes)

    @property
    def is_on(self) -> bool:
        return self.item.is_on

    @property
    def brightness(self) -> int | None:
        return self.item.brightness

    @property
    def effect(self) -> str | None:
        if self.item.control != CONTROL_MODES:
            return None
        return self.item.mode

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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.item.control == CONTROL_MODES:
            last = await self.async_get_last_state()
            if last is not None:
                self.item.restore_mode(last.attributes.get(ATTR_EFFECT))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.item.async_turn_on(
            mode=kwargs.get(ATTR_EFFECT),
            brightness=kwargs.get(ATTR_BRIGHTNESS),
            transition=kwargs.get(ATTR_TRANSITION),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.item.async_turn_off(transition=kwargs.get(ATTR_TRANSITION))
