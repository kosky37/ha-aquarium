from __future__ import annotations

DOMAIN = "aquarium"

SUBENTRY_LIGHT = "light"
SUBENTRY_DEVICE = "device"
SUBENTRY_SENSOR = "sensor"

CONF_ENTITY = "entity_id"
CONF_CONTROL = "control"
CONF_MODES = "modes"
CONF_TOGGLE_DELAY = "toggle_delay"
CONF_RESET_TIME = "reset_time"
CONF_SCHEDULE = "schedule"
CONF_TRANSITION = "transition"
CONF_KIND = "kind"
CONF_MIN = "min"
CONF_MAX = "max"

CONTROL_SWITCH = "switch"
CONTROL_DIMMABLE = "dimmable"
CONTROL_MODES = "modes"
CONTROLS = [CONTROL_SWITCH, CONTROL_DIMMABLE, CONTROL_MODES]

DEFAULT_TOGGLE_DELAY = 1.0
DEFAULT_RESET_TIME = 10.0
DEFAULT_TRANSITION = 0

DEVICE_KIND_ICONS = {
    "co2": "mdi:molecule-co2",
    "filter": "mdi:air-filter",
    "heater": "mdi:heating-coil",
    "pump": "mdi:pump",
    "air_pump": "mdi:chart-bubble",
    "uv": "mdi:lightbulb-fluorescent-tube-outline",
    "feeder": "mdi:fish",
    "other": "mdi:power-socket-eu",
}

SENSOR_KIND_ICONS = {
    "temperature": "mdi:thermometer-water",
    "ph": "mdi:ph",
    "tds": "mdi:water-opacity",
    "conductivity": "mdi:flash-triangle-outline",
    "oxygen": "mdi:gas-cylinder",
    "other": "mdi:gauge",
}

LIGHT_ICON = "mdi:lightbulb-on-outline"
