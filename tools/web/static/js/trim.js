import { $ } from "./utils.js";

// The trim lane is in source frames. The playback lane is in generated motion frames.
export function initTrim({ video, clock, seek }) {
  const start = $("trimStart"), end = $("trimEnd");
  const startValue = $("trimStartValue"), endValue = $("trimEndValue");
  const full = $("trimFull"), lane = $("trimRange");
  let active = false, editable = true, frames = 0, exact = false, capacity = 0;

  function sync() {
    const first = startValue.valueAsNumber || 1;
    const last = endValue.valueAsNumber || frames || first;
    const max = Math.max(1, frames), denominator = Math.max(1, max - 1);
    start.max = end.max = max;
    start.value = Math.min(max, first);
    end.value = Math.min(max, Math.max(first, last));
    lane.style.setProperty("--trim-start", (Number(start.value) - 1) / denominator);
    lane.style.setProperty("--trim-rest", (max - Number(end.value)) / denominator);
    start.disabled = end.disabled = !active || !editable || frames < 2;
    startValue.disabled = endValue.disabled = full.disabled = !active || !editable;
    start.setAttribute("aria-valuetext", `第 ${first} 帧`);
    end.setAttribute("aria-valuetext", endValue.value ? `第 ${last} 帧` : "自动到人物轨迹结束");
    const source = frames ? ` · 素材${exact ? "" : "约"} ${frames} 帧` : "";
    const range = first === 1 && !endValue.value ? "完整人物轨迹" : `第 ${first} 帧至${endValue.value ? `第 ${last} 帧` : "自动结束"}`;
    const limit = capacity && frames && last - first + 1 > capacity ? ` · 模型单段 ${capacity} 帧` : "";
    $("rangeSummary").textContent = `处理范围 · ${range}${source}${limit}`;
  }

  function estimate() {
    if (active && !exact && Number.isFinite(video.duration) && video.duration > 0) {
      frames = Math.max(1, Math.round((video.duration - clock.timeOf(0)) * 30));
      sync();
    }
  }
  for (const event of ["loadedmetadata", "durationchange", "flowhmr:clockready"]) video.addEventListener(event, estimate);

  start.addEventListener("input", () => {
    const first = Math.min(Number(start.value), endValue.valueAsNumber || frames);
    startValue.value = first;
    sync();
    seek(first - 1);
  });
  end.addEventListener("input", () => {
    const last = Math.max(Number(end.value), startValue.valueAsNumber || 1);
    endValue.value = last >= frames ? "" : last;
    sync();
    seek(last - 1);
  });
  for (const field of [startValue, endValue]) {
    field.addEventListener("input", sync);
    field.addEventListener("change", () => {
      const frame = field.valueAsNumber;
      if (Number.isSafeInteger(frame) && frame >= 1 && (!frames || frame <= frames)) seek(frame - 1);
    });
  }
  full.onclick = () => { startValue.value = 1; endValue.value = ""; sync(); };
  sync();

  return {
    begin() { active = editable = true; frames = 0; exact = false; sync(); },
    clear() { active = false; editable = true; frames = 0; exact = false; full.onclick(); },
    setCapacity(max) { capacity = max || 0; sync(); },
    setEditable(value) { if (editable !== value) { editable = value; sync(); } },
    setSource(count) {
      if (Number.isSafeInteger(count) && count > 0 && (frames !== count || !exact)) { frames = count; exact = true; sync(); }
    },
    apply(params) {
      startValue.value = (params.start_frame ?? 0) + 1;
      const oldLimit = params.auto_frames === false ? params.max_frames : null;
      const requested = params.end_frame == null ? null : params.end_frame + 1;
      endValue.value = (oldLimit && requested ? Math.min(oldLimit, requested) : oldLimit ?? requested) ?? "";
      sync();
    },
    read() {
      const first = startValue.valueAsNumber, last = endValue.value === "" && !endValue.validity.badInput ? null : endValue.valueAsNumber;
      if (!Number.isSafeInteger(first) || first < 1 || (last !== null && (!Number.isSafeInteger(last) || last < first))) {
        throw new Error("请设置有效的起止帧，结束帧也可留空自动检测。");
      }
      if (exact && (first > frames || (last !== null && last > frames))) throw new Error(`素材共 ${frames} 帧，请检查处理区间。`);
      return { auto_frames: true, start_frame: first - 1, end_frame: last === null ? null : last - 1 };
    },
  };
}
