import { describe, expect, test } from "bun:test";
import {
  DAY,
  defaultPoints,
  discover,
  fromMinutes,
  moveBoundary,
  normalize,
  pieces,
  removePoint,
  segmentAt,
  segments,
  serialize,
  setEnd,
  setStart,
  splitSegment,
  toMinutes,
  valueLabel,
} from "../custom_components/aquarium/frontend/aquarium-card.js";

const schedule = normalize([
  { at: "20:00", value: "off" },
  { at: "12:00", value: "Day" },
  { at: "19:00", value: "Daybreak" },
]);

describe("time helpers", () => {
  test("convert both ways", () => {
    expect(toMinutes("07:05")).toBe(425);
    expect(fromMinutes(425)).toBe("07:05");
    expect(fromMinutes(DAY + 30)).toBe("00:30");
  });
});

describe("segments", () => {
  test("are sorted and the last one wraps past midnight", () => {
    expect(schedule.map((p) => p.m)).toEqual([720, 1140, 1200]);
    const segs = segments(schedule);
    expect(segs[2]).toEqual({ index: 2, start: 1200, end: 720 + DAY, value: "off" });
    expect(pieces(segs[2])).toEqual([
      [1200, DAY],
      [0, 720],
    ]);
    expect(pieces(segs[0])).toEqual([[720, 1140]]);
  });

  test("segmentAt finds the active period, wrapping before the first change", () => {
    expect(segmentAt(schedule, 300)).toBe(2);
    expect(segmentAt(schedule, 720)).toBe(0);
    expect(segmentAt(schedule, 1150)).toBe(1);
  });
});

describe("editing", () => {
  test("dragging a boundary snaps and stays between its neighbours", () => {
    expect(moveBoundary(schedule, 1, 1103, 5)[1].m).toBe(1105);
    expect(moveBoundary(schedule, 1, 100, 5)[1].m).toBe(725);
    expect(moveBoundary(schedule, 1, 1300, 5)[1].m).toBe(1195);
    expect(moveBoundary(schedule, 2, 2000, 5)[2].m).toBe(DAY - 5);
    expect(moveBoundary(schedule, 0, -40, 5)[0].m).toBe(0);
  });

  test("split inserts a copy in the middle and returns its index", () => {
    const result = splitSegment(schedule, 0, 5);
    expect(result.points.map((p) => [fromMinutes(p.m), p.value])).toEqual([
      ["12:00", "Day"],
      ["15:30", "Day"],
      ["19:00", "Daybreak"],
      ["20:00", "off"],
    ]);
    expect(result.index).toBe(1);
    const night = splitSegment(schedule, 2, 5);
    expect(night.points.map((p) => fromMinutes(p.m))).toEqual(["04:00", "12:00", "19:00", "20:00"]);
    expect(night.points[night.index].value).toBe("off");
  });

  test("setting start and end moves the right boundaries", () => {
    expect(serialize(setStart(schedule, 1, toMinutes("18:30")))).toEqual([
      { at: "12:00", value: "Day" },
      { at: "18:30", value: "Daybreak" },
      { at: "20:00", value: "off" },
    ]);
    expect(setEnd(schedule, 2, toMinutes("11:00"))[0].m).toBe(660);
    expect(setEnd(schedule, 2, toMinutes("21:00"))).toBe(schedule);
    expect(setEnd(schedule, 0, toMinutes("18:00"))[1].m).toBe(1080);
  });

  test("remove merges into the previous period", () => {
    expect(serialize(removePoint(schedule, 1)).map((p) => p.at)).toEqual(["12:00", "20:00"]);
  });

  test("default schedules", () => {
    expect(serialize(defaultPoints({ control: "modes", modes: ["Day", "Night"] }))).toEqual([
      { at: "12:00", value: "Day" },
      { at: "20:00", value: "off" },
    ]);
    expect(defaultPoints({ control: "device", modes: [] })[0]).toEqual({ m: 660, value: "on" });
  });

  test("labels", () => {
    expect(valueLabel(40)).toBe("40%");
    expect(valueLabel("off")).toBe("Off");
    expect(valueLabel("Night")).toBe("Night");
  });
});

describe("discover", () => {
  test("groups the aquarium's devices and entities", () => {
    const hass = {
      devices: {
        hub: { id: "hub", name: "Aquarium", manufacturer: "Aquarium", model: "Aquarium", via_device_id: null },
        a: { id: "a", name: "Day&Night back", manufacturer: "Aquarium", model: "Light", via_device_id: "hub" },
        b: { id: "b", name: "CO2", manufacturer: "Aquarium", model: "CO2", via_device_id: "hub" },
        c: { id: "c", name: "Water", manufacturer: "Aquarium", model: "Temperature sensor", via_device_id: "hub" },
        x: { id: "x", name: "Other", manufacturer: "Other", model: "X", via_device_id: null },
      },
      entities: {
        "light.dn": { entity_id: "light.dn", device_id: "a", platform: "aquarium" },
        "select.dn_mode": { entity_id: "select.dn_mode", device_id: "a", platform: "aquarium", translation_key: "mode" },
        "switch.dn_schedule": { entity_id: "switch.dn_schedule", device_id: "a", platform: "aquarium", translation_key: "schedule" },
        "button.dn_reset": { entity_id: "button.dn_reset", device_id: "a", platform: "aquarium", translation_key: "reset_mode" },
        "switch.co2": { entity_id: "switch.co2", device_id: "b", platform: "aquarium" },
        "switch.co2_schedule": { entity_id: "switch.co2_schedule", device_id: "b", platform: "aquarium", translation_key: "schedule" },
        "sensor.water": { entity_id: "sensor.water", device_id: "c", platform: "aquarium" },
        "binary_sensor.water_out": { entity_id: "binary_sensor.water_out", device_id: "c", platform: "aquarium", translation_key: "out_of_range" },
      },
      states: {
        "light.dn": { attributes: { control: "modes", modes: ["Day", "Daybreak", "Night"] } },
        "switch.co2": { attributes: { kind: "co2", control: "device" } },
      },
    };
    const model = discover(hass, {});
    expect(model.name).toBe("Aquarium");
    expect(model.items.map((i) => [i.name, i.control, i.mode, i.schedule, i.reset ?? null])).toEqual([
      ["Day&Night back", "modes", "select.dn_mode", "switch.dn_schedule", "button.dn_reset"],
      ["CO2", "device", undefined, "switch.co2_schedule", null],
    ]);
    expect(model.items[1].icon).toBe("mdi:molecule-co2");
    expect(model.sensors).toEqual([{ id: "c", name: "Water", entity: "sensor.water", problem: "binary_sensor.water_out" }]);
    expect(discover({ devices: {}, entities: {}, states: {} })).toBeNull();
  });
});
