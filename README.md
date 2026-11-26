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

The integration can't read the lamp's mode, so it works it out from the plug's off and on changes. While it is switching modes itself, and for a few seconds after, it ignores the plug's status reports, because some plugs report an extra off and on after a command. If the lamp ever shows a different mode, press **Reset mode**: the lamp stays off longer than the reset time and comes back in the first mode.

## Dashboard card

The integration comes with an **Aquarium** card, loaded automatically. Add it from the card picker, or with:

```yaml
type: custom:aquarium-card
```

- **Header** with the aquarium's sensors, which turn red when out of range. Tap one for its history.
- **A row per light and device**: power button, what it is doing now and what happens next, mode buttons for lamps with modes, a brightness slider for dimmable lights, a Reset mode button, and an **Auto** switch to pause the schedule.
- **A 24-hour timeline** per row, with a red line at the current time.
  - Drag the edge between two periods to move the change.
  - Tap a period to set its exact times, choose its mode or brightness, split it in two, or merge it into the previous one.
  - Changes are drafts until you press **Save**, and take effect right away when saved.

Options: `aquarium` (which aquarium, when you have more than one), `title`, and `snap` (minutes per step when dragging, default 5).

The card saves schedules through the `aquarium.set_schedule` action, which you can also use in scripts.

## Entities

| Item | Entities |
| --- | --- |
| Light | light (with brightness or the modes as effects), Mode select and Reset mode button for lamps with modes, Schedule switch, Next change sensor |
| Device | switch, Schedule switch, Next change sensor |
| Sensor | sensor, Out of range binary sensor when limits are set |
