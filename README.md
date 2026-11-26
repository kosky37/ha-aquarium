# Aquarium for Home Assistant

A Home Assistant integration that groups an aquarium's lights, equipment and sensors, and runs their daily schedules.

## What it does

- **Lights**, any number, each with its own schedule. Three ways to control them:
  - **On/off**: a smart plug or switch.
  - **Dimmable**: a smart light with brightness, with an optional fade for scheduled changes.
  - **Modes by power cycling**: lamps such as the Aquael LEDDY DAY & NIGHT that switch mode when they are turned off and on again quickly. The integration tracks the current mode and toggles the plug as many times as needed to reach the mode you ask for.
- **Devices** such as CO2, filters, heaters, pumps or feeders, switched by a smart plug, with an optional schedule.
- **Sensors** such as water temperature or pH, shown with the aquarium, with optional minimum and maximum limits that raise an Out of range alert.
- Manual control of every light and device from Home Assistant. A manual change lasts until the next scheduled change.
- A **Schedule** switch per light and device to pause its schedule, and a **Next change** sensor showing what happens next.

## Installation

In the Home Assistant Marketplace (or HACS), add this repository as a custom integration repository, install **Aquarium** and restart Home Assistant. Then add it under **Settings → Devices & services → Add integration → Aquarium**.

To install by hand, copy `custom_components/aquarium` into your Home Assistant `config/custom_components` folder and restart.

## Setup

1. Add the integration and give the aquarium a name.
2. On the integration page, use **Add light**, **Add device** and **Add sensor**.
3. Edit any item later from its menu with **Edit**.

### Schedules

One change per line, as the time followed by the value:

```
11:00 Daybreak
12:00 Day
19:00 Daybreak
20:00 off
```

| Item | Values |
| --- | --- |
| On/off light, device | `on`, `off` |
| Dimmable light | `on`, `off`, a brightness such as `60%` |
| Light with modes | `on`, `off`, a mode name |

After a restart, the integration checks every item against its schedule and only changes what differs.

### Lights with modes

- **Modes**: in the order the lamp goes through them. The first one is the mode the lamp starts in after being off for a while.
- **Delay between toggles**: how long to wait after each off and each on while switching modes.
- **Off time that resets the mode**: if the lamp stays off at least this long, it starts again from the first mode.

The integration can't read the lamp's mode, so it works it out from the plug's off and on changes. If the lamp ever shows a different mode, turn it off for longer than the reset time and the count starts again.

## Entities

| Item | Entities |
| --- | --- |
| Light | light (with brightness or the modes as effects), Mode select for lamps with modes, Schedule switch, Next change sensor |
| Device | switch, Schedule switch, Next change sensor |
| Sensor | sensor, Out of range binary sensor when limits are set |
