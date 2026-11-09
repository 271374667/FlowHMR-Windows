// "Settings" card: person selection, camera mode, sampling and post-processing.
import { $, show } from "./utils.js";

const MAX_SMOOTHING_FRAMES = 3;
const validStrength = (value) => Number.isFinite(value) && value >= 0 && value <= 1;
const STORAGE = "flowhmr-generation-preferences";

function bindToggle(id) {
  const btn = $(id);
  btn.addEventListener("click", () => {
    btn.setAttribute("aria-checked", btn.getAttribute("aria-checked") === "true" ? "false" : "true");
  });
  return {
    get: () => btn.getAttribute("aria-checked") === "true",
    set: (v) => btn.setAttribute("aria-checked", v ? "true" : "false"),
  };
}

function samChunkSize(value) {
  if (typeof value === "string" && /^\d+$/.test(value.trim())) value = Number(value.trim());
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new Error("SAM 批次帧数须为正整数。");
  }
  return value;
}

export function initParams(defaults, manualBatchDefault) {
  const manual = bindToggle("optManual");
  const post = bindToggle("optPostprocess");
  const hamer = bindToggle("optHamer");
  const hamerButton = $("optHamer"), hamerStride = $("optHamerStride");
  const hamerSamplingSupported = defaults?.hamer_stride != null;
  const syncHamer = () => show("hamerSamplingRow", hamerSamplingSupported && !hamerButton.disabled && hamer.get());
  hamerButton.addEventListener("click", syncHamer);
  const soleFitSlider = $("optSoleFitStrength"), soleFit = $("optSoleFitValue");
  const autoBatch = bindToggle("optSamAuto");
  const cameraMode = $("optCameraMode");
  const footLockPreset = $("optFootLockPreset");
  const correctionGround = $("optCorrectionGround"), correctionHeight = $("optCorrectionHeight");
  const seed = $("optSeed"), cfg = $("optCfg"), stride = $("optVggt");
  const steps = $("optSteps"), samChunk = $("optSamChunk");
  const smoothingSlider = $("optSmoothing"), smoothing = $("optSmoothingValue");
  const smoothingHint = $("smoothingHint");
  let restoredSmoothingFrames = null;
  const readSmoothingFrames = () => restoredSmoothingFrames ?? Number((smoothing.valueAsNumber * MAX_SMOOTHING_FRAMES).toPrecision(15));
  function syncSmoothingSlider(legacyFrames = 0) {
    const value = smoothing.valueAsNumber;
    if (!validStrength(value)) return;
    smoothingSlider.value = value;
    const frames = Number(readSmoothingFrames().toPrecision(6));
    smoothingSlider.setAttribute("aria-valuetext", value === 0 ? "0，关闭" : `${value}，对应 ${frames} 帧`);
    smoothingHint.textContent = legacyFrames > MAX_SMOOTHING_FRAMES
      ? `原任务使用 ${legacyFrames} 帧；重跑时上限为 ${MAX_SMOOTHING_FRAMES} 帧。`
      : value === 0 ? `0 为关闭；1 对应 ${MAX_SMOOTHING_FRAMES} 帧。` : `当前对应 ${frames} 帧。`;
  }
  function smoothingEdited() {
    restoredSmoothingFrames = null;
    syncSmoothingSlider();
  }
  smoothingSlider.addEventListener("input", () => {
    smoothing.value = smoothingSlider.value;
    smoothingEdited();
  });
  smoothing.addEventListener("input", smoothingEdited);
  function syncSoleFitSlider() {
    const value = soleFit.valueAsNumber;
    if (!validStrength(value)) return;
    soleFitSlider.value = value;
    soleFitSlider.setAttribute("aria-valuetext", value === 0 ? "关闭" : soleFitSlider.value);
  }
  soleFitSlider.addEventListener("input", () => {
    soleFit.value = soleFitSlider.value;
    syncSoleFitSlider();
  });
  soleFit.addEventListener("input", syncSoleFitSlider);
  const syncBatch = () => {
    samChunk.disabled = autoBatch.get();
    show("samChunkRow", !samChunk.disabled);
  };
  $("optSamAuto").addEventListener("click", syncBatch);
  const syncCamera = () => {
    stride.disabled = cameraMode.value !== "manual";
    show("manualCameraRow", !stride.disabled);
    $("cameraHint").textContent = {
      auto: "按人物轨迹长度选择采样间隔。",
      static: "适用于无移动、无变焦的固定机位。",
      manual: "间隔越小，采样越密，显存开销越高。",
    }[cameraMode.value];
  };
  cameraMode.addEventListener("change", syncCamera);
  const syncCorrection = () => {
    const enabled = post.get() && !$("optPostprocess").disabled;
    show("footLockRow", enabled);
    show("soleFitRow", enabled);
    show("correctionFloorRow", enabled);
    show("correctionHeightRow", enabled && correctionGround.value === "manual");
    $("footLockHint").textContent = footLockPreset.value === "strong"
      ? "短暂丢失落脚信号时继续锁定；有意滑步时建议用标准。"
      : "锁住稳定落脚的脚底，保留自然过渡。";
  };
  $("optPostprocess").addEventListener("click", syncCorrection);
  footLockPreset.addEventListener("change", syncCorrection);
  correctionGround.addEventListener("change", syncCorrection);

  const apply = (p, correction, prefs) => {
    const chunkSize = samChunkSize(p.sam_chunk_size ?? prefs?.manualBatch ?? manualBatchDefault);
    manual.set(p.manual_select ?? true);
    post.set(!$("optPostprocess").disabled && !!p.postprocess);
    hamer.set(!hamerButton.disabled && !!p.hamer);
    hamerStride.value = p.hamer_stride ?? 1;
    syncHamer();
    soleFit.value = p.sole_fit_strength ?? (p.sole_fit ? 0.6 : 0);
    syncSoleFitSlider();
    footLockPreset.value = p.correction_preset === "strong" ? "strong" : "normal";
    correctionGround.value = p.correction_floor_m == null ? "auto" : "manual";
    correctionHeight.value = p.correction_floor_m ?? correction?.floor_m?.toFixed(3) ?? 0;
    autoBatch.set(p.sam_chunk_size == null);
    cameraMode.value = p.static_camera ? "static" : p.vggt_interval > 0 ? "manual" : "auto";
    seed.value = p.seed ?? 0;
    cfg.value = p.cfg_scale ?? 1.0;
    stride.value = p.vggt_interval > 0 ? p.vggt_interval : prefs?.manualInterval ?? 10;
    steps.value = p.steps ?? 20;
    const savedFrames = Number(p.smoothing_frames ?? 0);
    // Keep the saved frame value until edited, even when its strength is rounded for display.
    restoredSmoothingFrames = Number.isFinite(savedFrames) ? Math.min(MAX_SMOOTHING_FRAMES, Math.max(0, savedFrames)) : 0;
    smoothing.value = Number((restoredSmoothingFrames / MAX_SMOOTHING_FRAMES).toPrecision(4));
    syncSmoothingSlider(savedFrames);
    samChunk.value = chunkSize;
    syncBatch();
    syncCamera();
    syncCorrection();
  };
  const read = (overrides = {}, remember = false) => {
    const strength = soleFit.valueAsNumber;
    if (post.get() && !validStrength(strength)) throw new Error("脚掌贴地强度须为 0 到 1 的数字。");
    if (!validStrength(smoothing.valueAsNumber)) throw new Error("滤波强度须为 0 到 1 的数字。");
    const out = {
      manual_select: manual.get(),
      postprocess: post.get(),
      hamer: !hamerButton.disabled && hamer.get(),
      hamer_stride: Number(hamerStride.value),
      correction_preset: footLockPreset.value,
      sole_fit_strength: validStrength(strength) ? strength : 0,
      correction_floor_m: !remember && post.get() && correctionGround.value === "manual" ? correctionHeight.valueAsNumber : null,
      static_camera: cameraMode.value === "static",
      seed: parseInt(seed.value, 10),
      cfg_scale: parseFloat(cfg.value),
      vggt_interval: overrides.vggt_interval ?? (cameraMode.value === "manual" ? Number(stride.value) : 0),
      sam_chunk_size: autoBatch.get() ? null : samChunkSize(samChunk.value),
      steps: parseInt(steps.value, 10),
      smoothing_frames: readSmoothingFrames(),
    };
    if (!Number.isInteger(out.seed) || out.seed < 0 || out.seed > 2147483647) throw new Error("随机种子须为 0 到 2147483647 的整数。");
    if (out.correction_floor_m !== null && !Number.isFinite(out.correction_floor_m)) throw new Error("请输入修正地面的高度（米）。");
    if (!Number.isFinite(out.cfg_scale) || out.cfg_scale < 0 || out.cfg_scale > 10) throw new Error("CFG 须在 0 到 10 之间。");
    if (overrides.vggt_interval == null && cameraMode.value === "manual" && (!Number.isInteger(out.vggt_interval) || out.vggt_interval < 1 || out.vggt_interval > 120)) {
      throw new Error("手动相机采样间隔须为 1 到 120 帧。");
    }
    if (!Number.isInteger(out.steps) || out.steps < 1 || out.steps > 100) throw new Error("ODE 步数须为 1 到 100 的整数。");
    return out;
  };

  let remembered = null, jobId = null;
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE) || "null");
    if (saved?.params && typeof saved.params === "object") {
      apply({ ...defaults, ...saved.params, correction_floor_m: null }, null, saved);
      read({}, true);
      remembered = saved;
    }
  } catch { /* Invalid or unavailable local preferences: use the defaults. */ }
  if (!remembered) apply(defaults || {});

  function rememberSettings() {
    try {
      const { correction_floor_m, ...params } = read({}, true);
      const manualBatch = samChunk.valueAsNumber;
      const manualInterval = stride.valueAsNumber;
      remembered = { jobId, params,
        manualBatch: Number.isSafeInteger(manualBatch) && manualBatch > 0 ? manualBatch : manualBatchDefault,
        manualInterval: Number.isInteger(manualInterval) && manualInterval >= 1 && manualInterval <= 120 ? manualInterval : 10,
      };
      localStorage.setItem(STORAGE, JSON.stringify(remembered));
    } catch { /* Do not remember an incomplete edit. */ }
  }
  for (const input of [seed, cfg, stride, steps, samChunk, smoothingSlider, smoothing, soleFitSlider, soleFit]) {
    input.addEventListener("input", rememberSettings);
  }
  for (const input of [cameraMode, footLockPreset, hamerStride]) input.addEventListener("change", rememberSettings);
  for (const id of ["optManual", "optPostprocess", "optHamer", "optSamAuto"]) $(id).addEventListener("click", rememberSettings);

  const suggestCorrectionHeight = (report) => {
    if (report?.automatic && correctionGround.value === "auto") correctionHeight.value = report.floor_m.toFixed(3);
  };

  return { read, suggestCorrectionHeight,
    refreshHamer() {
      if (hamerButton.disabled) hamer.set(false);
      syncHamer();
    },
    openJob(id, params, correction, restoreDraft) {
      jobId = id;
      const draft = restoreDraft && remembered?.jobId === id ? remembered : null;
      apply({ ...params, ...draft?.params }, correction, draft);
    },
    reset() { apply(defaults || {}); rememberSettings(); },
    newSource() {
      jobId = null;
      if (remembered) {
        apply({ ...defaults, ...remembered.params, correction_floor_m: null }, null, remembered);
        return;
      }
      // A manual floor belongs to the previous video.
      correctionGround.value = "auto";
      correctionHeight.value = 0;
      syncCorrection();
    },
  };
}
