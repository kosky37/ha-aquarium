from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTROL,
    CONF_ENTITY,
    CONF_KIND,
    CONF_MAX,
    CONF_MIN,
    CONF_MODES,
    CONF_RESET_TIME,
    CONF_SCHEDULE,
    CONF_TOGGLE_DELAY,
    CONF_TRANSITION,
    CONTROL_DIMMABLE,
    CONTROL_MODES,
    CONTROL_SWITCH,
    DEFAULT_RESET_TIME,
    DEFAULT_TOGGLE_DELAY,
    DEFAULT_TRANSITION,
    SUBENTRY_DEVICE,
    SUBENTRY_LIGHT,
)
from .schedule import (
    OFF,
    ON,
    Point,
    Value,
    dimmable_parser,
    format_schedule,
    modes_parser,
    next_change,
    parse_schedule,
    steps_to_mode,
    switch_parser,
    value_at,
)

_LOGGER = logging.getLogger(__name__)

WAIT_TIMEOUT = 15.0
BRIGHTNESS_TOLERANCE = 3


class Item:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        self.hass = hass
        self.entry = entry
        self.subentry = subentry
        self.data: dict[str, Any] = dict(subentry.data)
        self.name = subentry.title
        self.target: str = self.data[CONF_ENTITY]
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def subentry_id(self) -> str:
        return self.subentry.subentry_id

    @property
    def kind(self) -> str | None:
        return self.data.get(CONF_KIND)

    @property
    def target_state(self) -> State | None:
        return self.hass.states.get(self.target)

    @property
    def available(self) -> bool:
        state = self.target_state
        return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    @callback
    def add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def async_start(self) -> None:
        self._unsubs.append(
            async_track_state_change_event(self.hass, [self.target], self._target_changed)
        )

    @callback
    def async_stop(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    @callback
    def _target_changed(self, event: Event[EventStateChangedData]) -> None:
        self.notify()


class SensorItem(Item):
    @property
    def minimum(self) -> float | None:
        return self.data.get(CONF_MIN)

    @property
    def maximum(self) -> float | None:
        return self.data.get(CONF_MAX)

    @property
    def value(self) -> float | None:
        state = self.target_state
        if state is None:
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    @property
    def available(self) -> bool:
        return self.value is not None


class ScheduledItem(Item):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        super().__init__(hass, entry, subentry)
        self.points: list[Point] = parse_schedule(self.data.get(CONF_SCHEDULE), self.parser())
        self.schedule_enabled = True
        self._lock = asyncio.Lock()

    def parser(self) -> Callable[[str], Value]:
        return switch_parser

    @property
    def is_on(self) -> bool:
        state = self.target_state
        return state is not None and state.state == STATE_ON

    @property
    def schedule_text(self) -> str:
        return format_schedule(self.points)

    @property
    def next_change(self) -> tuple[datetime, Value] | None:
        return next_change(self.points, dt_util.now())

    @property
    def scheduled_value(self) -> Value | None:
        return value_at(self.points, dt_util.now())

    @callback
    def async_start(self) -> None:
        super().async_start()
        for point in self.points:
            self._unsubs.append(
                async_track_time_change(
                    self.hass,
                    self._point_job(point.value),
                    hour=point.at.hour,
                    minute=point.at.minute,
                    second=0,
                )
            )
        self._unsubs.append(async_at_started(self.hass, self._started))

    def _point_job(self, value: Value) -> Callable[[datetime], Any]:
        async def run(now: datetime) -> None:
            self.notify()
            if self.schedule_enabled:
                await self._safe(self.async_apply(value))

        return run

    async def _started(self, hass: HomeAssistant) -> None:
        if self.schedule_enabled:
            await self._safe(self.async_reconcile())

    async def _safe(self, job: Any) -> None:
        try:
            await job
        except (HomeAssistantError, TimeoutError) as err:
            _LOGGER.warning("%s: could not apply the schedule: %s", self.name, err)

    async def async_set_schedule_enabled(self, enabled: bool) -> None:
        self.schedule_enabled = enabled
        self.notify()
        if enabled:
            await self.async_reconcile()

    @callback
    def restore_schedule_enabled(self, enabled: bool) -> None:
        self.schedule_enabled = enabled

    async def async_reconcile(self) -> None:
        value = self.scheduled_value
        if value is None or not self.available:
            return
        if not self.matches(value):
            await self.async_apply(value)

    def matches(self, value: Value) -> bool:
        return self.is_on == (value != OFF)

    async def async_apply(self, value: Value) -> None:
        if value == OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._power(False)

    async def _power(self, on: bool, data: dict[str, Any] | None = None, domain: str | None = None) -> None:
        await self.hass.services.async_call(
            domain or self.target.split(".", 1)[0],
            "turn_on" if on else "turn_off",
            {"entity_id": self.target, **(data or {})},
            blocking=True,
        )

    async def _wait_for(self, on: bool) -> None:
        wanted = STATE_ON if on else STATE_OFF
        state = self.target_state
        if state is not None and state.state == wanted:
            return
        future: asyncio.Future[None] = self.hass.loop.create_future()

        @callback
        def check(event: Event[EventStateChangedData]) -> None:
            new = event.data["new_state"]
            if new is not None and new.state == wanted and not future.done():
                future.set_result(None)

        unsub = async_track_state_change_event(self.hass, [self.target], check)
        try:
            state = self.target_state
            if state is not None and state.state == wanted:
                return
            async with asyncio.timeout(WAIT_TIMEOUT):
                await future
        except TimeoutError as err:
            raise HomeAssistantError(f"{self.target} did not turn {wanted} in time") from err
        finally:
            unsub()


class DeviceItem(ScheduledItem):
    pass


class LightItem(ScheduledItem):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        self.control: str = subentry.data.get(CONF_CONTROL, CONTROL_SWITCH)
        self.modes: list[str] = list(subentry.data.get(CONF_MODES) or [])
        self.toggle_delay = float(subentry.data.get(CONF_TOGGLE_DELAY, DEFAULT_TOGGLE_DELAY))
        self.reset_time = float(subentry.data.get(CONF_RESET_TIME, DEFAULT_RESET_TIME))
        self.transition = float(subentry.data.get(CONF_TRANSITION, DEFAULT_TRANSITION) or 0)
        self.mode_index = 0
        self._off_since: datetime | None = None
        super().__init__(hass, entry, subentry)

    def parser(self) -> Callable[[str], Value]:
        if self.control == CONTROL_DIMMABLE:
            return dimmable_parser
        if self.control == CONTROL_MODES:
            return modes_parser(self.modes)
        return switch_parser

    @property
    def mode(self) -> str | None:
        if self.control != CONTROL_MODES or not self.modes:
            return None
        return self.modes[self.mode_index % len(self.modes)]

    @property
    def brightness(self) -> int | None:
        state = self.target_state
        if self.control != CONTROL_DIMMABLE or state is None or state.state != STATE_ON:
            return None
        return state.attributes.get("brightness")

    @callback
    def async_start(self) -> None:
        state = self.target_state
        if state is not None and state.state == STATE_OFF:
            self._off_since = state.last_changed
        super().async_start()

    @callback
    def restore_mode(self, mode: str | None) -> None:
        if mode in self.modes:
            self.mode_index = self.modes.index(mode)

    @callback
    def _target_changed(self, event: Event[EventStateChangedData]) -> None:
        if self.control == CONTROL_MODES:
            self._track_mode(event.data["old_state"], event.data["new_state"])
        super()._target_changed(event)

    def _track_mode(self, old: State | None, new: State | None) -> None:
        if new is None or not self.modes:
            return
        if new.state == STATE_OFF and (old is None or old.state != STATE_OFF):
            self._off_since = new.last_changed
            return
        if new.state == STATE_ON and old is not None and old.state == STATE_OFF:
            off_for = None
            if self._off_since is not None:
                off_for = (new.last_changed - self._off_since).total_seconds()
            if off_for is not None and off_for < self.reset_time:
                self.mode_index = (self.mode_index + 1) % len(self.modes)
            else:
                self.mode_index = 0

    def matches(self, value: Value) -> bool:
        if value == OFF:
            return not self.is_on
        if not self.is_on:
            return False
        if value == ON:
            return True
        if self.control == CONTROL_DIMMABLE and isinstance(value, int):
            brightness = self.brightness
            if brightness is None:
                return False
            return abs(round(brightness * 100 / 255) - value) <= BRIGHTNESS_TOLERANCE
        if self.control == CONTROL_MODES:
            return self.mode == value
        return True

    async def async_apply(self, value: Value) -> None:
        if value == OFF:
            await self.async_turn_off(transition=self.transition)
        elif value == ON:
            await self.async_turn_on(transition=self.transition)
        elif isinstance(value, int):
            await self.async_turn_on(brightness_pct=value, transition=self.transition)
        else:
            await self.async_turn_on(mode=value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        mode = kwargs.get("mode")
        if self.control == CONTROL_MODES:
            await self._set_mode(mode)
            return
        if self.control == CONTROL_DIMMABLE:
            data: dict[str, Any] = {}
            if kwargs.get("brightness_pct") is not None:
                data["brightness_pct"] = kwargs["brightness_pct"]
            if kwargs.get("brightness") is not None:
                data["brightness"] = kwargs["brightness"]
            if kwargs.get("transition"):
                data["transition"] = kwargs["transition"]
            await self._power(True, data, "light")
            return
        await self._power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.control == CONTROL_DIMMABLE and kwargs.get("transition"):
            await self._power(False, {"transition": kwargs["transition"]}, "light")
            return
        async with self._lock:
            await self._power(False)

    async def _set_mode(self, mode: str | None) -> None:
        async with self._lock:
            if not self.is_on:
                await self._power(True)
                await self._wait_for(True)
                await asyncio.sleep(self.toggle_delay)
            if mode is None or mode not in self.modes:
                return
            steps = steps_to_mode(self.mode_index, self.modes.index(mode), len(self.modes))
            for _ in range(steps):
                await self._power(False)
                await self._wait_for(False)
                await asyncio.sleep(self.toggle_delay)
                await self._power(True)
                await self._wait_for(True)
                await asyncio.sleep(self.toggle_delay)
            self.notify()


def build_item(hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> Item:
    if subentry.subentry_type == SUBENTRY_LIGHT:
        return LightItem(hass, entry, subentry)
    if subentry.subentry_type == SUBENTRY_DEVICE:
        return DeviceItem(hass, entry, subentry)
    return SensorItem(hass, entry, subentry)
