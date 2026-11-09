const DEFAULTS = { source: 0.17, properties: 0.22, history: 0.30, timeline: 0.15 };
const LIMITS = { source: 158, properties: 218, viewport: 305, history: 128, details: 150, timeline: 94, top: 225 };
const STORAGE = "flowhmr-layout-ratios";

// The separators share grid tracks with their editors, so both axes resize in place.
export function initLayout() {
  const workspace = document.querySelector(".workspace");
  const dividers = [...workspace.querySelectorAll("[data-split]")];
  const prefs = { ...DEFAULTS };
  const dimensions = () => ({ columns: Math.max(1, workspace.clientWidth - 12),
    timeline: Math.max(1, workspace.clientHeight - 8), history: Math.max(1, workspace.clientHeight - 10) });
  const widthSide = (side) => side === "source" || side === "properties";
  const extent = (side, area) => widthSide(side) ? area.columns : area[side];
  const clamp = (value, minimum, maximum) => Math.min(Math.max(minimum, maximum), Math.max(minimum, Math.round(value)));
  const save = () => localStorage.setItem(STORAGE, JSON.stringify(prefs));
  const area = dimensions();
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE) || "null");
    for (const side of Object.keys(DEFAULTS)) {
      const previous = widthSide(side) ? Number(localStorage.getItem(`flowhmr-${side}-width`)) / area.columns : 0;
      const ratio = stored?.[side] ?? previous;
      if (Number.isFinite(ratio) && ratio > 0 && ratio < 1) prefs[side] = ratio;
    }
  } catch { /* use the editor defaults */ }

  let sizes = {};
  function render() {
    if (workspace.clientWidth <= 770) return;
    const a = dimensions();
    const sideRoom = Math.max(LIMITS.source + LIMITS.properties, a.columns - LIMITS.viewport);
    let source = Math.max(LIMITS.source, Math.round(a.columns * prefs.source));
    let properties = Math.max(LIMITS.properties, Math.round(a.columns * prefs.properties));
    if (source + properties > sideRoom) {
      const spare = source + properties - LIMITS.source - LIMITS.properties;
      source = LIMITS.source + Math.round((source - LIMITS.source) / spare * (sideRoom - LIMITS.source - LIMITS.properties));
      properties = sideRoom - source;
    }
    sizes = { source, properties,
      history: clamp(a.history * prefs.history, LIMITS.history, a.history - LIMITS.details),
      timeline: clamp(a.timeline * prefs.timeline, LIMITS.timeline, a.timeline - LIMITS.top) };
    for (const divider of dividers) {
      const side = divider.dataset.split;
      workspace.style.setProperty(`--${side}-size`, `${sizes[side]}px`);
      divider.setAttribute("aria-valuenow", String(Math.round(sizes[side] / extent(side, a) * 100)));
    }
  }

  function resize(side, requested) {
    const a = dimensions();
    let maximum;
    if (widthSide(side)) {
      const neighbor = side === "source" ? "properties" : "source";
      prefs[neighbor] = sizes[neighbor] / a.columns;
      maximum = a.columns - sizes[neighbor] - LIMITS.viewport;
    } else maximum = a[side] - LIMITS[side === "timeline" ? "top" : "details"];
    prefs[side] = clamp(requested, LIMITS[side], maximum) / extent(side, a);
    render();
  }

  for (const splitter of dividers) {
    const side = splitter.dataset.split;
    const vertical = widthSide(side);
    const direction = side === "source" || side === "history" ? 1 : -1;
    const position = (event) => vertical ? event.clientX : event.clientY;
    let drag = null;
    splitter.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      splitter.focus({ preventScroll: true });
      splitter.setPointerCapture(event.pointerId);
      drag = { pos: position(event), size: sizes[side], pointer: event.pointerId };
      splitter.classList.add("dragging");
    });
    splitter.addEventListener("pointermove", (event) => {
      if (drag?.pointer === event.pointerId) resize(side, drag.size + direction * (position(event) - drag.pos));
    });
    splitter.addEventListener("pointerup", (event) => {
      if (drag?.pointer === event.pointerId) resize(side, drag.size + direction * (position(event) - drag.pos));
    });
    splitter.addEventListener("lostpointercapture", () => {
      if (drag) save();
      drag = null;
      splitter.classList.remove("dragging");
    });
    splitter.addEventListener("dblclick", () => {
      prefs[side] = DEFAULTS[side];
      render();
      save();
    });
    splitter.addEventListener("keydown", (event) => {
      const [minus, plus] = vertical ? ["ArrowLeft", "ArrowRight"] : ["ArrowUp", "ArrowDown"];
      if (event.key !== minus && event.key !== plus) return;
      event.stopPropagation();
      event.preventDefault();
      resize(side, sizes[side] + direction * (event.key === plus ? 12 : -12));
      save();
    });
  }
  new ResizeObserver(render).observe(workspace);
  render();
}
