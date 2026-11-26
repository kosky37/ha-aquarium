from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

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
    CONTROLS,
    DEFAULT_RESET_TIME,
    DEFAULT_TOGGLE_DELAY,
    DEFAULT_TRANSITION,
    DEVICE_KIND_ICONS,
    DOMAIN,
    SENSOR_KIND_ICONS,
    SUBENTRY_DEVICE,
    SUBENTRY_LIGHT,
    SUBENTRY_SENSOR,
)
from .schedule import (
    ScheduleError,
    Value,
    dimmable_parser,
    format_schedule,
    modes_parser,
    parse_schedule,
    switch_parser,
)

SWITCHABLE_DOMAINS = ["switch", "light", "fan", "input_boolean"]
SCHEDULE_SELECTOR = TextSelector(TextSelectorConfig(multiline=True))


def _select(options: list[str], key: str) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(options=options, translation_key=key, mode=SelectSelectorMode.DROPDOWN)
    )


def _seconds(minimum: float, maximum: float, step: float) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
        )
    )


def _check_schedule(
    text: str, parser: Callable[[str], Value], errors: dict[str, str], placeholders: dict[str, str]
) -> str:
    try:
        return format_schedule(parse_schedule(text, parser))
    except ScheduleError as err:
        errors[CONF_SCHEDULE] = "invalid_schedule"
        placeholders["line"] = str(err.line)
        placeholders["reason"] = err.reason
        return text


class AquariumConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data={})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_NAME, default="Aquarium"): str}),
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            SUBENTRY_LIGHT: LightSubentryFlow,
            SUBENTRY_DEVICE: DeviceSubentryFlow,
            SUBENTRY_SENSOR: SensorSubentryFlow,
        }


class _ItemFlow(ConfigSubentryFlow):
    def _defaults(self) -> dict[str, Any]:
        if self.source == "reconfigure":
            subentry = self._get_reconfigure_subentry()
            return {CONF_NAME: subentry.title, **subentry.data}
        return {}

    def _finish(self, title: str, data: dict[str, Any]) -> SubentryFlowResult:
        if self.source == "reconfigure":
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=title, data=data
            )
        return self.async_create_entry(title=title, data=data)


class LightSubentryFlow(_ItemFlow):
    def __init__(self) -> None:
        self._base: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        defaults = self._defaults()
        if user_input is not None:
            self._base = user_input
            return await self.async_step_details()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
                    vol.Required(CONF_CONTROL, default=defaults.get(CONF_CONTROL, CONTROL_SWITCH)): _select(
                        CONTROLS, "control"
                    ),
                }
            ),
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self.async_step_user(user_input)

    async def async_step_details(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        control = self._base[CONF_CONTROL]
        defaults = self._defaults() if self._defaults().get(CONF_CONTROL) == control else {}
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"line": "", "reason": ""}
        if user_input is not None:
            data = {CONF_CONTROL: control, **user_input}
            parser: Callable[[str], Value] = switch_parser
            if control == CONTROL_DIMMABLE:
                parser = dimmable_parser
            elif control == CONTROL_MODES:
                modes = [mode.strip() for mode in user_input.get(CONF_MODES, []) if mode.strip()]
                data[CONF_MODES] = modes
                if len(modes) < 2 or len({mode.lower() for mode in modes}) != len(modes):
                    errors[CONF_MODES] = "invalid_modes"
                if float(user_input.get(CONF_TOGGLE_DELAY, 0)) >= float(user_input.get(CONF_RESET_TIME, 0)):
                    errors[CONF_RESET_TIME] = "reset_too_short"
                parser = modes_parser(modes)
            data[CONF_SCHEDULE] = _check_schedule(
                user_input.get(CONF_SCHEDULE, ""), parser, errors, placeholders
            )
            if not errors:
                return self._finish(self._base[CONF_NAME], data)
            defaults = data
        schema: dict[Any, Any] = {
            vol.Required(CONF_ENTITY, default=defaults.get(CONF_ENTITY, vol.UNDEFINED)): EntitySelector(
                EntitySelectorConfig(domain=["light"] if control == CONTROL_DIMMABLE else SWITCHABLE_DOMAINS)
            ),
        }
        if control == CONTROL_MODES:
            schema[vol.Required(CONF_MODES, default=defaults.get(CONF_MODES, ["Day", "Daybreak", "Night"]))] = (
                TextSelector(TextSelectorConfig(multiple=True))
            )
            schema[vol.Required(CONF_TOGGLE_DELAY, default=defaults.get(CONF_TOGGLE_DELAY, DEFAULT_TOGGLE_DELAY))] = (
                _seconds(0.2, 10, 0.1)
            )
            schema[vol.Required(CONF_RESET_TIME, default=defaults.get(CONF_RESET_TIME, DEFAULT_RESET_TIME))] = (
                _seconds(1, 300, 1)
            )
        if control == CONTROL_DIMMABLE:
            schema[vol.Optional(CONF_TRANSITION, default=defaults.get(CONF_TRANSITION, DEFAULT_TRANSITION))] = (
                _seconds(0, 3600, 1)
            )
        schema[vol.Optional(CONF_SCHEDULE, default=defaults.get(CONF_SCHEDULE, ""))] = SCHEDULE_SELECTOR
        return self.async_show_form(
            step_id="details",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders=placeholders,
        )


class DeviceSubentryFlow(_ItemFlow):
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        defaults = self._defaults()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"line": "", "reason": ""}
        if user_input is not None:
            data = dict(user_input)
            name = data.pop(CONF_NAME)
            data[CONF_SCHEDULE] = _check_schedule(data.get(CONF_SCHEDULE, ""), switch_parser, errors, placeholders)
            if not errors:
                return self._finish(name, data)
            defaults = {CONF_NAME: name, **data}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
                    vol.Required(CONF_KIND, default=defaults.get(CONF_KIND, "co2")): _select(
                        list(DEVICE_KIND_ICONS), "device_kind"
                    ),
                    vol.Required(CONF_ENTITY, default=defaults.get(CONF_ENTITY, vol.UNDEFINED)): EntitySelector(
                        EntitySelectorConfig(domain=SWITCHABLE_DOMAINS)
                    ),
                    vol.Optional(CONF_SCHEDULE, default=defaults.get(CONF_SCHEDULE, "")): SCHEDULE_SELECTOR,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self.async_step_user(user_input)


class SensorSubentryFlow(_ItemFlow):
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        defaults = self._defaults()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            name = data.pop(CONF_NAME)
            low, high = data.get(CONF_MIN), data.get(CONF_MAX)
            if low is not None and high is not None and low >= high:
                errors[CONF_MAX] = "max_not_above_min"
            else:
                return self._finish(name, data)
            defaults = {CONF_NAME: name, **data}
        number = NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, step="any"))
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
                    vol.Required(CONF_KIND, default=defaults.get(CONF_KIND, "temperature")): _select(
                        list(SENSOR_KIND_ICONS), "sensor_kind"
                    ),
                    vol.Required(CONF_ENTITY, default=defaults.get(CONF_ENTITY, vol.UNDEFINED)): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(
                        CONF_MIN,
                        description={"suggested_value": defaults.get(CONF_MIN)},
                    ): number,
                    vol.Optional(
                        CONF_MAX,
                        description={"suggested_value": defaults.get(CONF_MAX)},
                    ): number,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self.async_step_user(user_input)
