export const DAY = 1440;
export const DEFAULT_SNAP = 5;

const MODE_COLORS = ["#ffd54f", "#ff8a65", "#7986cb", "#4db6ac", "#ba68c8", "#90a4ae"];
const KIND_COLORS = {
  co2: "#81c784",
  filter: "#4fc3f7",
  heater: "#e57373",
  pump: "#4dd0e1",
  air_pump: "#90caf9",
  uv: "#ce93d8",
  feeder: "#ffb74d",
  other: "#b0bec5",
};
const LIGHT_COLOR = "#ffc107";
const KIND_ICONS = {
  co2: "mdi:molecule-co2",
  filter: "mdi:air-filter",
  heater: "mdi:heating-coil",
  pump: "mdi:pump",
  air_pump: "mdi:chart-bubble",
  uv: "mdi:lightbulb-fluorescent-tube-outline",
  feeder: "mdi:fish",
  other: "mdi:power-socket-eu",
};

export function toMinutes(text) {
  const [h, m] = String(text).split(":").map(Number);
  return h * 60 + m;
}

export function fromMinutes(minutes) {
  const value = ((Math.round(minutes) % DAY) + DAY) % DAY;
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

export function normalize(points) {
  return (points || [])
    .map((p) => ({ m: typeof p.m === "number" ? p.m : toMinutes(p.at), value: p.value }))
    .sort((a, b) => a.m - b.m);
}

export function serialize(points) {
  return points.map((p) => ({ at: fromMinutes(p.m), value: p.value }));
}

export function samePoints(a, b) {
  return a.length === b.length && a.every((p, i) => p.m === b[i].m && p.value === b[i].value);
}

export function segments(points) {
  const n = points.length;
  return points.map((p, i) => ({
    index: i,
    start: p.m,
    end: i + 1 < n ? points[i + 1].m : points[0].m + DAY,
    value: p.value,
  }));
}

export function pieces(segment) {
  if (segment.end <= DAY) return [[segment.start, segment.end]];
  const out = [];
  if (segment.start < DAY) out.push([segment.start, DAY]);
  out.push([0, segment.end - DAY]);
  return out.filter(([a, b]) => b > a);
}

export function segmentAt(points, minute) {
  if (!points.length) return -1;
  let index = points.length - 1;
  for (let i = 0; i < points.length; i += 1) {
    if (points[i].m <= minute) index = i;
  }
  return index;
}

export function snapTo(minute, snap) {
  return Math.round(minute / snap) * snap;
}

export function boundsFor(points, index, snap) {
  const low = index > 0 ? points[index - 1].m + snap : 0;
  const high = index < points.length - 1 ? points[index + 1].m - snap : DAY - snap;
  return [low, high];
}

export function moveBoundary(points, index, minute, snap = DEFAULT_SNAP) {
  const [low, high] = boundsFor(points, index, snap);
  const target = Math.min(high, Math.max(low, snapTo(minute, snap)));
  return points.map((p, i) => (i === index ? { ...p, m: target } : p));
}

export function splitSegment(points, index, snap = DEFAULT_SNAP) {
  const seg = segments(points)[index];
  if (!seg) return { points, index };
  const length = seg.end - seg.start;
  if (length < snap * 2) return { points, index };
  let middle = snapTo(seg.start + length / 2, snap) % DAY;
  if (middle === seg.start) middle = (seg.start + snap) % DAY;
  const next = normalize([...points, { m: middle, value: seg.value }]);
  return { points: next, index: next.findIndex((p) => p.m === middle) };
}

export function removePoint(points, index) {
  return points.filter((_, i) => i !== index);
}

export function setValue(points, index, value) {
  return points.map((p, i) => (i === index ? { ...p, value } : p));
}

export function setStart(points, index, minute, snap = DEFAULT_SNAP) {
  return moveBoundary(points, index, minute, snap);
}

export function setEnd(points, index, minute, snap = DEFAULT_SNAP) {
  if (points.length < 2) return points;
  const next = (index + 1) % points.length;
  if (next === 0) {
    const [, high] = boundsFor(points, 0, snap);
    const target = snapTo(minute, snap);
    if (target > high || target < 0) return points;
    return points.map((p, i) => (i === 0 ? { ...p, m: target } : p));
  }
  return moveBoundary(points, next, minute, snap);
}

export function defaultPoints(item) {
  if (item.control === "modes" && item.modes.length) {
    return [
      { m: 720, value: item.modes[0] },
      { m: 1200, value: "off" },
    ];
  }
  if (item.control === "device") {
    return [
      { m: 660, value: "on" },
      { m: 1140, value: "off" },
    ];
  }
  if (item.control === "dimmable") {
    return [
      { m: 720, value: 100 },
      { m: 1200, value: "off" },
    ];
  }
  return [
    { m: 720, value: "on" },
    { m: 1200, value: "off" },
  ];
}

export function valueLabel(value) {
  if (typeof value === "number") return `${value}%`;
  if (value === "off") return "Off";
  if (value === "on") return "On";
  return String(value);
}

export function valueOptions(item) {
  if (item.control === "modes") return ["off", ...item.modes];
  if (item.control === "dimmable") return ["off", 25, 50, 75, 100];
  return ["off", "on"];
}

export function valueColor(item, value) {
  if (value === "off" || value === undefined || value === null) return null;
  if (typeof value === "number") {
    return `color-mix(in srgb, ${LIGHT_COLOR} ${Math.round(30 + 0.7 * value)}%, transparent)`;
  }
  if (item.control === "modes") {
    const index = item.modes.indexOf(value);
    return MODE_COLORS[(index < 0 ? 0 : index) % MODE_COLORS.length];
  }
  if (item.control === "device") return KIND_COLORS[item.kind] || KIND_COLORS.other;
  return LIGHT_COLOR;
}

export function durationLabel(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!h) return `${m} min`;
  return m ? `${h} h ${m} min` : `${h} h`;
}

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function nowMinutes(timeZone) {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date());
    const h = Number(parts.find((p) => p.type === "hour").value);
    const m = Number(parts.find((p) => p.type === "minute").value);
    return h * 60 + m;
  } catch (err) {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
}

function timeOf(iso, timeZone) {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
  } catch (err) {
    return "";
  }
}

export function discover(hass, config = {}) {
  const devices = Object.values(hass.devices || {});
  const entities = Object.values(hass.entities || {}).filter((e) => e.platform === "aquarium");
  const deviceIds = new Set(entities.map((e) => e.device_id));
  const hubs = devices.filter((d) => d.manufacturer === "Aquarium" && d.model === "Aquarium");
  let hub = null;
  if (config.aquarium) {
    hub = hubs.find((d) => d.id === config.aquarium || d.name_by_user === config.aquarium || d.name === config.aquarium) || null;
  }
  if (!hub) hub = hubs[0] || null;
  if (!hub) return null;
  const items = [];
  const sensors = [];
  for (const device of devices) {
    if (device.via_device_id !== hub.id || !deviceIds.has(device.id)) continue;
    const own = entities.filter((e) => e.device_id === device.id);
    const find = (domain, key) => own.find((e) => e.entity_id.startsWith(`${domain}.`) && (e.translation_key || null) === key);
    const name = device.name_by_user || device.name;
    const light = find("light", null);
    const deviceSwitch = find("switch", null);
    const mirror = find("sensor", null);
    if (light || deviceSwitch) {
      const main = (light || deviceSwitch).entity_id;
      const attrs = hass.states[main]?.attributes || {};
      const control = light ? attrs.control || "switch" : "device";
      items.push({
        id: device.id,
        name,
        main,
        control,
        kind: attrs.kind || null,
        modes: Array.isArray(attrs.modes) ? attrs.modes : [],
        icon: light ? "mdi:lightbulb-on-outline" : KIND_ICONS[attrs.kind] || KIND_ICONS.other,
        mode: find("select", "mode")?.entity_id,
        schedule: find("switch", "schedule")?.entity_id,
        reset: find("button", "reset_mode")?.entity_id,
      });
    } else if (mirror) {
      sensors.push({
        id: device.id,
        name,
        entity: mirror.entity_id,
        problem: find("binary_sensor", "out_of_range")?.entity_id,
      });
    }
  }
  const rank = (item) => (item.control === "device" ? 1 : 0);
  items.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  sensors.sort((a, b) => a.name.localeCompare(b.name));
  return { hub, name: hub.name_by_user || hub.name, items, sensors };
}

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; overflow: hidden; }
  .top { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .title { font-size: 1.25rem; font-weight: 500; flex: 1 1 auto; display: flex; align-items: center; gap: 8px; }
  .title ha-icon { color: var(--state-icon-color, var(--primary-color)); }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 16px; background: rgba(var(--rgb-primary-text-color, 255,255,255), 0.06); font-size: 0.875rem; cursor: pointer; border: 1px solid transparent; }
  .chip b { font-weight: 600; }
  .chip.bad { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
  .chip ha-icon { --mdc-icon-size: 18px; }
  .axis { position: relative; height: 16px; margin: 0 2px 2px; font-size: 0.7rem; color: var(--secondary-text-color); }
  .axis span { position: absolute; transform: translateX(-50%); }
  .axis span:first-child { transform: none; }
  .axis span:last-child { transform: translateX(-100%); }
  .row { padding: 10px 0 12px; border-top: 1px solid var(--divider-color); }
  .axis + .row { border-top: none; }
  .head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
  .power { width: 40px; height: 40px; border-radius: 50%; border: none; display: grid; place-items: center; cursor: pointer; background: rgba(var(--rgb-primary-text-color, 255,255,255), 0.08); color: var(--secondary-text-color); flex: 0 0 auto; transition: background 0.2s, color 0.2s; }
  .power.on { background: color-mix(in srgb, var(--c) 30%, transparent); color: var(--c); }
  .power:disabled { opacity: 0.4; cursor: default; }
  .info { flex: 1 1 160px; min-width: 0; cursor: pointer; }
  .name { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .status { font-size: 0.85rem; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .quick { display: flex; align-items: center; gap: 8px; flex: 0 1 auto; }
  .modes { display: inline-flex; border-radius: 18px; overflow: hidden; border: 1px solid var(--divider-color); }
  .modes button { border: none; background: transparent; color: var(--primary-text-color); padding: 6px 12px; font: inherit; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
  .modes button + button { border-left: 1px solid var(--divider-color); }
  .modes button .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--c); }
  .modes button.active { background: color-mix(in srgb, var(--c) 28%, transparent); font-weight: 600; }
  .modes button.pending { animation: pulse 1s infinite; }
  @keyframes pulse { 50% { opacity: 0.4; } }
  .bright { width: 140px; accent-color: ${LIGHT_COLOR}; }
  .icon-btn { border: none; background: transparent; color: var(--secondary-text-color); cursor: pointer; border-radius: 50%; width: 34px; height: 34px; display: grid; place-items: center; }
  .icon-btn:hover { background: rgba(var(--rgb-primary-text-color, 255,255,255), 0.08); }
  .icon-btn.armed { color: var(--error-color, #db4437); }
  .auto { display: inline-flex; align-items: center; gap: 6px; font-size: 0.8rem; color: var(--secondary-text-color); cursor: pointer; user-select: none; }
  .toggle { position: relative; width: 34px; height: 20px; border-radius: 10px; background: rgba(var(--rgb-primary-text-color, 255,255,255), 0.2); transition: background 0.2s; }
  .toggle::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform 0.2s; }
  .auto.on .toggle { background: var(--primary-color); }
  .auto.on .toggle::after { transform: translateX(14px); }
  .track { position: relative; height: 34px; border-radius: 8px; margin: 0 2px; touch-action: pan-y; user-select: none;
    background-color: rgba(var(--rgb-primary-text-color, 255,255,255), 0.04);
    background-image: repeating-linear-gradient(to right, rgba(var(--rgb-primary-text-color, 255,255,255), 0.08) 0 1px, transparent 1px 12.5%); }
  .track.paused .seg { filter: saturate(0.25); opacity: 0.6; }
  .seg { position: absolute; top: 3px; bottom: 3px; background: var(--c); border-radius: 5px; cursor: pointer; display: flex; align-items: center; justify-content: center; overflow: hidden; color: rgba(0,0,0,0.75); font-size: 0.75rem; font-weight: 600; box-sizing: border-box; }
  .seg.off { background: repeating-linear-gradient(135deg, transparent 0 6px, rgba(var(--rgb-primary-text-color, 255,255,255), 0.06) 6px 12px); color: var(--secondary-text-color); font-weight: 400; }
  .seg.selected { outline: 2px solid var(--primary-color); outline-offset: 1px; z-index: 1; }
  .seg span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 4px; pointer-events: none; }
  .handle { position: absolute; top: -3px; bottom: -3px; width: 18px; margin-left: -9px; cursor: ew-resize; z-index: 2; touch-action: none; display: flex; justify-content: center; outline: none; }
  .handle::before { content: ""; width: 4px; border-radius: 2px; background: var(--primary-text-color); opacity: 0.55; transition: opacity 0.15s, width 0.15s; }
  .handle:hover::before, .handle:focus-visible::before, .handle.drag::before { opacity: 1; width: 6px; }
  .tip { position: absolute; bottom: calc(100% + 4px); left: 50%; transform: translateX(-50%); background: var(--primary-text-color); color: var(--card-background-color, #1c1c1c); font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; white-space: nowrap; opacity: 0; pointer-events: none; transition: opacity 0.15s; }
  .handle:hover .tip, .handle:focus-visible .tip, .handle.drag .tip { opacity: 1; }
  .now { position: absolute; top: -4px; bottom: -4px; width: 2px; margin-left: -1px; background: var(--error-color, #db4437); border-radius: 1px; pointer-events: none; z-index: 3; }
  .empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.85rem; color: var(--secondary-text-color); }
  .link { border: none; background: none; color: var(--primary-color); font: inherit; cursor: pointer; padding: 4px 6px; }
  .editor { margin: 10px 2px 0; padding: 12px; border-radius: 10px; background: rgba(var(--rgb-primary-text-color, 255,255,255), 0.05); display: grid; gap: 10px; }
  .editor .times { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.9rem; }
  .editor input[type=time] { font: inherit; color: var(--primary-text-color); background: var(--card-background-color, transparent); border: 1px solid var(--divider-color); border-radius: 6px; padding: 4px 6px; color-scheme: dark light; }
  .editor .dur { color: var(--secondary-text-color); font-size: 0.85rem; }
  .values { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .value { border: 1px solid var(--divider-color); background: transparent; color: var(--primary-text-color); border-radius: 16px; padding: 5px 12px; font: inherit; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
  .value .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--c); border: 1px solid rgba(var(--rgb-primary-text-color, 255,255,255), 0.3); }
  .value.active { border-color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 18%, transparent); font-weight: 600; }
  .editor .actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
  .btn { border: 1px solid var(--divider-color); background: transparent; color: var(--primary-text-color); border-radius: 18px; padding: 6px 14px; font: inherit; font-size: 0.85rem; cursor: pointer; }
  .btn.primary { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .btn:disabled { opacity: 0.4; cursor: default; }
  .save { position: sticky; bottom: 0; display: flex; align-items: center; gap: 8px; margin: 12px -16px -16px; padding: 10px 16px; background: color-mix(in srgb, var(--primary-color) 14%, var(--ha-card-background, var(--card-background-color, #1c1c1c))); }
  .save .msg { flex: 1; font-size: 0.9rem; }
  .save .err { color: var(--error-color, #db4437); }
  .note { font-size: 0.8rem; color: var(--secondary-text-color); }
  .missing { padding: 8px 0; color: var(--secondary-text-color); }
  @media (max-width: 520px) {
    .quick { order: 3; flex-basis: 100%; overflow-x: auto; }
    .bright { flex: 1; }
  }
`;

function defineCard() {
  class AquariumCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._drafts = new Map();
      this._selected = null;
      this._drag = null;
      this._pending = new Map();
      this._armed = null;
      this._saving = false;
      this._error = "";
      this._structure = "";
      this._timer = null;
    }

    setConfig(config) {
      this._config = { snap: DEFAULT_SNAP, ...(config || {}) };
      this._structure = "";
      this._update();
    }

    set hass(hass) {
      this._hass = hass;
      this._update();
    }

    getCardSize() {
      return 2 + 2 * (this._model?.items.length || 3);
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6, rows: "auto" };
    }

    static getStubConfig() {
      return {};
    }

    static getConfigElement() {
      return document.createElement("aquarium-card-editor");
    }

    connectedCallback() {
      this._timer = setInterval(() => this._refreshTracks(), 30000);
    }

    disconnectedCallback() {
      clearInterval(this._timer);
    }

    get _snap() {
      return Number(this._config?.snap) || DEFAULT_SNAP;
    }

    _state(entityId) {
      return entityId ? this._hass?.states[entityId] : undefined;
    }

    _points(item) {
      if (this._drafts.has(item.id)) return this._drafts.get(item.id);
      return normalize(this._state(item.main)?.attributes.schedule_points || []);
    }

    _setDraft(item, points) {
      const saved = normalize(this._state(item.main)?.attributes.schedule_points || []);
      if (samePoints(points, saved)) this._drafts.delete(item.id);
      else this._drafts.set(item.id, points);
    }

    _update() {
      if (!this._hass || !this._config) return;
      this._model = discover(this._hass, this._config);
      const signature = JSON.stringify(this._model && [this._model.name, this._model.items.map((i) => [i.id, i.name, i.control, i.modes, i.mode, i.schedule, i.reset]), this._model.sensors.map((s) => [s.id, s.name])]);
      if (signature !== this._structure) {
        this._structure = signature;
        this._build();
      }
      this._refresh();
    }

    _build() {
      const root = this.shadowRoot;
      const model = this._model;
      if (!model) {
        root.innerHTML = `<style>${STYLE}</style><ha-card><div class="missing">No aquarium found. Add one under Settings → Devices &amp; services → Aquarium.</div></ha-card>`;
        return;
      }
      const hours = [0, 3, 6, 9, 12, 15, 18, 21, 24];
      root.innerHTML = `
        <style>${STYLE}</style>
        <ha-card>
          <div class="top">
            <div class="title"><ha-icon icon="mdi:fishbowl-outline"></ha-icon><span>${esc(this._config.title || model.name)}</span></div>
            <div class="chips"></div>
          </div>
          <div class="axis">${hours.map((h) => `<span style="left:${(h / 24) * 100}%">${String(h).padStart(2, "0")}</span>`).join("")}</div>
          ${model.items.map((item) => `
            <div class="row" data-id="${esc(item.id)}">
              <div class="head">
                <button class="power" data-act="power" style="--c:${valueColor(item, item.control === "modes" ? item.modes[0] : "on") || LIGHT_COLOR}"><ha-icon icon="${esc(item.icon)}"></ha-icon></button>
                <div class="info" data-act="more"><div class="name">${esc(item.name)}</div><div class="status"></div></div>
                <div class="quick"></div>
                ${item.reset ? `<button class="icon-btn" data-act="reset" title="Reset mode"><ha-icon icon="mdi:restart"></ha-icon></button>` : ""}
                ${item.schedule ? `<label class="auto" data-act="auto" title="Follow the schedule"><span class="toggle"></span><span>Auto</span></label>` : ""}
              </div>
              <div class="track"></div>
              <div class="editor" hidden></div>
            </div>`).join("")}
          ${model.items.length ? "" : `<div class="missing">Add lights and devices under Settings → Devices &amp; services → Aquarium.</div>`}
          <div class="save" hidden></div>
        </ha-card>`;
      root.querySelectorAll(".row").forEach((row) => this._wireRow(row));
      root.querySelector(".chips").addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (chip) this._moreInfo(chip.dataset.entity);
      });
      root.querySelector(".save").addEventListener("click", (e) => {
        const act = e.target.closest("[data-save]")?.dataset.save;
        if (act === "save") this._save();
        if (act === "discard") {
          this._drafts.clear();
          this._selected = null;
          this._error = "";
          this._refresh();
        }
      });
    }

    _item(id) {
      return this._model?.items.find((i) => i.id === id);
    }

    _wireRow(row) {
      const id = row.dataset.id;
      row.querySelector(".head").addEventListener("click", (e) => {
        const item = this._item(id);
        const target = e.target.closest("[data-act]");
        if (!item || !target) return;
        const act = target.dataset.act;
        if (act === "power") this._togglePower(item);
        if (act === "more") this._moreInfo(item.main);
        if (act === "auto") {
          e.preventDefault();
          this._call("switch", "toggle", { entity_id: item.schedule });
        }
        if (act === "mode") this._setMode(item, target.dataset.mode);
        if (act === "reset") this._reset(item, target);
      });
      row.querySelector(".head").addEventListener("change", (e) => {
        const item = this._item(id);
        if (item && e.target.matches(".bright")) {
          this._call("light", "turn_on", { entity_id: item.main, brightness_pct: Number(e.target.value) });
        }
      });
      const track = row.querySelector(".track");
      track.addEventListener("pointerdown", (e) => this._pointerDown(id, track, e));
      track.addEventListener("pointermove", (e) => this._pointerMove(id, track, e));
      track.addEventListener("pointerup", (e) => this._pointerUp(id, track, e));
      track.addEventListener("pointercancel", () => this._endDrag());
      track.addEventListener("keydown", (e) => this._keyDown(id, e));
      track.addEventListener("click", (e) => {
        if (e.target.closest("[data-act=add]")) {
          const item = this._item(id);
          this._drafts.set(id, defaultPoints(item));
          this._selected = { id, index: 0 };
          this._refresh();
        }
      });
      const editor = row.querySelector(".editor");
      editor.addEventListener("click", (e) => this._editorClick(id, e));
      editor.addEventListener("change", (e) => this._editorChange(id, e));
      editor.addEventListener("input", (e) => {
        if (e.target.matches("[data-ed=level]")) {
          const label = editor.querySelector(".level");
          if (label) label.textContent = `${e.target.value}%`;
        }
      });
    }

    _minuteAt(track, clientX) {
      const rect = track.getBoundingClientRect();
      return ((clientX - rect.left) / rect.width) * DAY;
    }

    _pointerDown(id, track, e) {
      const handle = e.target.closest(".handle");
      const seg = e.target.closest(".seg");
      this._press = { id, x: e.clientX, y: e.clientY, seg: seg ? Number(seg.dataset.i) : null };
      if (handle) {
        e.preventDefault();
        this._drag = { id, index: Number(handle.dataset.i), pointer: e.pointerId };
        track.setPointerCapture(e.pointerId);
        this._renderTrack(id);
      }
    }

    _pointerMove(id, track, e) {
      if (!this._drag || this._drag.id !== id || this._drag.pointer !== e.pointerId) return;
      const item = this._item(id);
      const points = moveBoundary(this._points(item), this._drag.index, this._minuteAt(track, e.clientX), this._snap);
      this._setDraft(item, points);
      this._renderTrack(id);
      this._renderSave();
      if (this._selected?.id === id) this._renderEditor(id);
    }

    _pointerUp(id, track, e) {
      if (this._drag && this._drag.id === id) {
        if (track.hasPointerCapture(e.pointerId)) track.releasePointerCapture(e.pointerId);
        this._endDrag();
        return;
      }
      const press = this._press;
      this._press = null;
      if (!press || press.id !== id || press.seg === null) return;
      if (Math.abs(e.clientX - press.x) > 6 || Math.abs(e.clientY - press.y) > 6) return;
      const same = this._selected && this._selected.id === id && this._selected.index === press.seg;
      this._selected = same ? null : { id, index: press.seg };
      this._refresh();
    }

    _endDrag() {
      if (!this._drag) return;
      const id = this._drag.id;
      this._drag = null;
      this._renderTrack(id);
    }

    _keyDown(id, e) {
      const handle = e.target.closest(".handle");
      if (!handle) return;
      const step = e.shiftKey ? 60 : this._snap;
      const delta = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
      if (!delta) return;
      e.preventDefault();
      const item = this._item(id);
      const index = Number(handle.dataset.i);
      const points = this._points(item);
      this._setDraft(item, moveBoundary(points, index, points[index].m + delta, this._snap));
      this._renderTrack(id);
      this._renderSave();
      if (this._selected?.id === id) this._renderEditor(id);
      this.shadowRoot.querySelector(`.row[data-id="${CSS.escape(id)}"] .handle[data-i="${index}"]`)?.focus();
    }

    _editorClick(id, e) {
      const target = e.target.closest("[data-ed]");
      if (!target || !this._selected) return;
      const item = this._item(id);
      const points = this._points(item);
      const index = this._selected.index;
      const act = target.dataset.ed;
      if (act === "value") {
        const raw = target.dataset.value;
        const value = item.control === "dimmable" && raw !== "off" && raw !== "on" ? Number(raw) : raw;
        this._setDraft(item, setValue(points, index, value));
      } else if (act === "split") {
        const result = splitSegment(points, index, this._snap);
        this._setDraft(item, result.points);
        this._selected = { id, index: result.index };
      } else if (act === "remove") {
        const next = removePoint(points, index);
        this._setDraft(item, next);
        this._selected = next.length ? { id, index: Math.max(0, index - 1) } : null;
      } else if (act === "close") {
        this._selected = null;
      } else {
        return;
      }
      this._refresh();
    }

    _editorChange(id, e) {
      if (!this._selected) return;
      const item = this._item(id);
      const points = this._points(item);
      const index = this._selected.index;
      const ed = e.target.dataset.ed;
      if (ed === "start" && e.target.value) {
        const moved = setStart(points, index, toMinutes(e.target.value), this._snap);
        this._setDraft(item, moved);
      } else if (ed === "end" && e.target.value) {
        this._setDraft(item, setEnd(points, index, toMinutes(e.target.value), this._snap));
      } else if (ed === "level") {
        this._setDraft(item, setValue(points, index, Number(e.target.value)));
      } else {
        return;
      }
      this._refresh();
    }

    _togglePower(item) {
      const domain = item.main.split(".")[0];
      this._call(domain, "toggle", { entity_id: item.main });
    }

    _setMode(item, mode) {
      if (!item.mode) return;
      this._pending.set(item.id, { mode, until: Date.now() + 30000 });
      this._renderQuick(item);
      this._call("select", "select_option", { entity_id: item.mode, option: mode }).finally(() => {
        this._pending.delete(item.id);
        this._refresh();
      });
    }

    _reset(item, button) {
      if (this._armed === item.id) {
        this._armed = null;
        button.classList.remove("armed");
        button.title = "Reset mode";
        this._pending.set(item.id, { mode: item.modes[0], until: Date.now() + 60000 });
        this._renderQuick(item);
        this._call("button", "press", { entity_id: item.reset }).finally(() => {
          this._pending.delete(item.id);
          this._refresh();
        });
        return;
      }
      this._armed = item.id;
      button.classList.add("armed");
      button.title = "Tap again: the lamp goes off for a moment and restarts in its first mode";
      setTimeout(() => {
        if (this._armed === item.id) {
          this._armed = null;
          button.classList.remove("armed");
          button.title = "Reset mode";
        }
      }, 4000);
    }

    async _save() {
      if (this._saving || !this._drafts.size) return;
      this._saving = true;
      this._error = "";
      this._renderSave();
      try {
        for (const [id, points] of [...this._drafts.entries()]) {
          const item = this._item(id);
          if (!item) continue;
          await this._hass.callService("aquarium", "set_schedule", { entity_id: item.main, schedule: serialize(points) });
          this._drafts.delete(id);
        }
        this._selected = null;
      } catch (err) {
        this._error = err?.message || String(err);
      } finally {
        this._saving = false;
        this._refresh();
      }
    }

    _call(domain, service, data) {
      return this._hass.callService(domain, service, data).catch((err) => {
        this._error = err?.message || String(err);
        this._renderSave();
      });
    }

    _moreInfo(entityId) {
      if (!entityId) return;
      this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId } }));
    }

    _refresh() {
      if (!this._model) return;
      this._renderChips();
      for (const item of this._model.items) {
        this._renderHead(item);
        this._renderQuick(item);
        this._renderTrack(item.id);
        this._renderEditor(item.id);
      }
      this._renderSave();
    }

    _refreshTracks() {
      if (!this._model || this._drag) return;
      for (const item of this._model.items) this._renderTrack(item.id);
    }

    _row(id) {
      return this.shadowRoot.querySelector(`.row[data-id="${CSS.escape(id)}"]`);
    }

    _renderChips() {
      const box = this.shadowRoot.querySelector(".chips");
      if (!box) return;
      box.innerHTML = this._model.sensors.map((sensor) => {
        const state = this._state(sensor.entity);
        const bad = this._state(sensor.problem)?.state === "on";
        const unit = state?.attributes.unit_of_measurement || "";
        const icon = state?.attributes.icon || "mdi:gauge";
        const value = !state || ["unavailable", "unknown"].includes(state.state) ? "–" : state.state;
        return `<span class="chip ${bad ? "bad" : ""}" data-entity="${esc(sensor.entity)}" title="${bad ? "Out of range" : ""}"><ha-icon icon="${esc(icon)}"></ha-icon>${esc(sensor.name)} <b>${esc(value)}${unit ? ` ${esc(unit)}` : ""}</b></span>`;
      }).join("");
    }

    _statusText(item) {
      const state = this._state(item.main);
      if (!state || state.state === "unavailable") return "Unavailable";
      const a = state.attributes;
      let now = "Off";
      if (state.state === "on") {
        if (item.control === "modes") now = a.effect || "On";
        else if (item.control === "dimmable" && a.brightness) now = `${Math.round((a.brightness / 255) * 100)}%`;
        else now = "On";
      }
      const tz = this._hass.config?.time_zone;
      const auto = this._state(item.schedule)?.state !== "off";
      if (!item.schedule || !(a.schedule_points || []).length) return `${now} · no schedule`;
      if (!auto) return `${now} · manual, schedule paused`;
      if (a.next_change) return `${now} · ${valueLabel(a.next_value)} at ${timeOf(a.next_change, tz)}`;
      return now;
    }

    _renderHead(item) {
      const row = this._row(item.id);
      if (!row) return;
      const state = this._state(item.main);
      const on = state?.state === "on";
      const power = row.querySelector(".power");
      power.classList.toggle("on", on);
      power.disabled = !state || state.state === "unavailable";
      power.title = on ? "Turn off" : "Turn on";
      let color = valueColor(item, "on") || LIGHT_COLOR;
      if (item.control === "modes" && on) color = valueColor(item, state.attributes.effect || item.modes[0]) || color;
      power.style.setProperty("--c", color);
      row.querySelector(".status").textContent = this._statusText(item);
      const auto = row.querySelector(".auto");
      if (auto) auto.classList.toggle("on", this._state(item.schedule)?.state !== "off");
    }

    _renderQuick(item) {
      const box = this._row(item.id)?.querySelector(".quick");
      if (!box) return;
      if (box.contains(this.shadowRoot.activeElement) && item.control === "dimmable") return;
      const state = this._state(item.main);
      if (item.control === "modes" && item.mode) {
        const pending = this._pending.get(item.id);
        const current = state?.state === "on" ? state.attributes.effect : null;
        box.innerHTML = `<div class="modes">${item.modes.map((mode) => `<button data-act="mode" data-mode="${esc(mode)}" class="${mode === current ? "active" : ""} ${pending?.mode === mode ? "pending" : ""}" style="--c:${valueColor(item, mode)}"><span class="dot"></span>${esc(mode)}</button>`).join("")}</div>`;
      } else if (item.control === "dimmable") {
        const pct = state?.state === "on" && state.attributes.brightness ? Math.round((state.attributes.brightness / 255) * 100) : 0;
        box.innerHTML = `<input class="bright" type="range" min="1" max="100" value="${pct || 1}" title="Brightness">`;
      } else {
        box.innerHTML = "";
      }
    }

    _renderTrack(id) {
      const item = this._item(id);
      const row = this._row(id);
      if (!item || !row) return;
      const track = row.querySelector(".track");
      const points = this._points(item);
      const tz = this._hass.config?.time_zone;
      const now = nowMinutes(tz);
      const paused = this._state(item.schedule)?.state === "off";
      track.classList.toggle("paused", paused);
      if (!points.length) {
        track.innerHTML = `<div class="empty">No schedule <button class="link" data-act="add">Add a schedule</button></div><div class="now" style="left:${(now / DAY) * 100}%"></div>`;
        return;
      }
      const current = segmentAt(points, now);
      const selected = this._selected?.id === id ? this._selected.index : -1;
      const segs = segments(points).map((seg) => {
        const color = valueColor(item, seg.value);
        const label = valueLabel(seg.value);
        return pieces(seg).map(([a, b]) => {
          const width = ((b - a) / DAY) * 100;
          const text = width > 6 ? `<span>${esc(label)}</span>` : "";
          const cls = ["seg", color ? "" : "off", seg.index === selected ? "selected" : "", seg.index === current ? "current" : ""].join(" ");
          return `<div class="${cls}" data-i="${seg.index}" style="left:${(a / DAY) * 100}%;width:${width}%;${color ? `--c:${color}` : ""}" title="${esc(`${label}, ${fromMinutes(seg.start)}–${fromMinutes(seg.end)}`)}">${text}</div>`;
        }).join("");
      }).join("");
      const dragging = this._drag?.id === id ? this._drag.index : -1;
      const handles = points.map((p, i) => `<div class="handle ${i === dragging ? "drag" : ""}" data-i="${i}" tabindex="0" role="slider" aria-label="Change at" aria-valuetext="${fromMinutes(p.m)}" style="left:${(p.m / DAY) * 100}%"><span class="tip">${fromMinutes(p.m)}</span></div>`).join("");
      track.innerHTML = `${segs}${handles}<div class="now" style="left:${(now / DAY) * 100}%"></div>`;
    }

    _renderEditor(id) {
      const item = this._item(id);
      const editor = this._row(id)?.querySelector(".editor");
      if (!item || !editor) return;
      const points = this._points(item);
      if (!this._selected || this._selected.id !== id || !points[this._selected.index]) {
        if (this._selected?.id === id) this._selected = null;
        editor.hidden = true;
        editor.innerHTML = "";
        return;
      }
      if (editor.contains(this.shadowRoot.activeElement) && this.shadowRoot.activeElement.matches("input")) return;
      const index = this._selected.index;
      const seg = segments(points)[index];
      const value = seg.value;
      const options = valueOptions(item);
      const chips = options.map((option) => {
        const color = valueColor(item, option);
        const active = option === value;
        return `<button class="value ${active ? "active" : ""}" data-ed="value" data-value="${esc(option)}"><span class="dot" style="--c:${color || "transparent"}"></span>${esc(valueLabel(option))}</button>`;
      }).join("");
      const level = item.control === "dimmable" && typeof value === "number"
        ? `<input type="range" min="1" max="100" value="${value}" data-ed="level" class="bright"><span class="level">${value}%</span>`
        : "";
      const single = points.length === 1;
      editor.hidden = false;
      editor.innerHTML = `
        <div class="times">
          <input type="time" step="${this._snap * 60}" data-ed="start" value="${fromMinutes(seg.start)}" aria-label="From">
          <span>–</span>
          <input type="time" step="${this._snap * 60}" data-ed="end" value="${fromMinutes(seg.end)}" aria-label="Until" ${single ? "disabled" : ""}>
          <span class="dur">${single ? "all day" : durationLabel(seg.end - seg.start)}</span>
        </div>
        <div class="values">${chips}${level}</div>
        <div class="actions">
          <button class="btn" data-ed="split">Split in two</button>
          <button class="btn" data-ed="remove">${single ? "Clear schedule" : "Merge into previous"}</button>
          <button class="btn primary" data-ed="close">Done</button>
        </div>`;
    }

    _renderSave() {
      const bar = this.shadowRoot.querySelector(".save");
      if (!bar) return;
      const count = this._drafts.size;
      if (!count && !this._error) {
        bar.hidden = true;
        bar.innerHTML = "";
        return;
      }
      bar.hidden = false;
      const msg = this._error
        ? `<span class="msg err">${esc(this._error)}</span>`
        : `<span class="msg">${count === 1 ? "1 schedule changed" : `${count} schedules changed`}. Changes take effect as soon as you save.</span>`;
      bar.innerHTML = `${msg}<button class="btn" data-save="discard" ${this._saving ? "disabled" : ""}>${count ? "Discard" : "Dismiss"}</button>${count ? `<button class="btn primary" data-save="save" ${this._saving ? "disabled" : ""}>${this._saving ? "Saving…" : "Save"}</button>` : ""}`;
      if (!count && this._error) {
        bar.querySelector("[data-save=discard]").addEventListener("click", () => {
          this._error = "";
          this._renderSave();
        }, { once: true });
      }
    }
  }

  class AquariumCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = { ...(config || {}) };
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    _render() {
      if (!this._hass || !this._config) return;
      const hubs = Object.values(this._hass.devices || {}).filter((d) => d.manufacturer === "Aquarium" && d.model === "Aquarium");
      const key = JSON.stringify([hubs.map((h) => h.id), this._config]);
      if (key === this._key) return;
      this._key = key;
      this.innerHTML = `
        <div style="display:grid;gap:12px;padding:8px 0">
          <label style="display:grid;gap:4px">Aquarium
            <select data-key="aquarium" style="font:inherit;padding:6px">
              ${hubs.map((h) => `<option value="${esc(h.id)}" ${this._config.aquarium === h.id ? "selected" : ""}>${esc(h.name_by_user || h.name)}</option>`).join("")}
            </select>
          </label>
          <label style="display:grid;gap:4px">Title (optional)
            <input data-key="title" value="${esc(this._config.title || "")}" style="font:inherit;padding:6px">
          </label>
          <label style="display:grid;gap:4px">Time step when dragging (minutes)
            <select data-key="snap" style="font:inherit;padding:6px">
              ${[1, 5, 10, 15, 30].map((n) => `<option value="${n}" ${Number(this._config.snap || DEFAULT_SNAP) === n ? "selected" : ""}>${n}</option>`).join("")}
            </select>
          </label>
        </div>`;
      this.querySelectorAll("[data-key]").forEach((el) => el.addEventListener("change", () => {
        const next = { ...this._config };
        const value = el.dataset.key === "snap" ? Number(el.value) : el.value;
        if (value === "" || value === undefined) delete next[el.dataset.key];
        else next[el.dataset.key] = value;
        this._config = next;
        this.dispatchEvent(new CustomEvent("config-changed", { bubbles: true, composed: true, detail: { config: next } }));
      }));
    }
  }

  if (!customElements.get("aquarium-card")) customElements.define("aquarium-card", AquariumCard);
  if (!customElements.get("aquarium-card-editor")) customElements.define("aquarium-card-editor", AquariumCardEditor);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "aquarium-card")) {
    window.customCards.push({
      type: "aquarium-card",
      name: "Aquarium",
      description: "Lights, devices, sensors and daily schedules of an aquarium.",
      preview: false,
      documentationURL: "https://github.com/kosky37/ha-aquarium",
    });
  }
}

if (typeof window !== "undefined" && window.customElements) defineCard();
