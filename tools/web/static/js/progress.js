// "Pipeline" card: queue state, per-stage progress bars and elapsed time, errors.
import { $, show, el, formatSeconds, STATUS_LABEL, jobLabel } from "./utils.js";

const STAGE_LABEL = { Detection: "人物检测", Camera: "相机估计", "Static camera": "固定机位", "Body features": "SAM 特征", Generation: "动作生成", "Hand refinement": "手指精修" };
const MESSAGES = {
  "Starting": "正在准备视频", "Starting generation": "正在生成动作", "Building 3D mesh": "正在构建 3D 预览",
  "Cancelled": "任务已停止", "Run stopped when FlowHMR restarted.": "任务已停止，素材和已完成的缓存已保留",
  "Stop requested; stopping at the next safe step": "正在停止，已完成的缓存会保留",
};

export function initProgress() {
  const list = $("stageList");

  function renderStages(stages, now) {
    list.innerHTML = "";
    for (const s of stages) {
      const row = el("li", `stage ${s.status}`);
      row.title = s.detail || "";
      row.append(el("span", "stage-dot"), el("span", "stage-label", STAGE_LABEL[s.label] || s.label));
      const bar = el("div", "stage-bar");
      const fill = el("div", "stage-fill");
      fill.style.width = `${s.status === "completed" ? 100 : s.progress}%`;
      bar.append(fill);
      row.append(bar);
      row.append(el("span", "stage-pct num", `${s.status === "completed" ? 100 : Math.round(s.progress)}%`));
      let t = formatSeconds(s.elapsed_seconds);
      if (s.start) t = formatSeconds(Math.max(0,
        (s.end || s.paused_at || now) - s.start - (s.paused_seconds || 0)));
      if (s.status === "waiting_user") t = "等待";
      row.append(el("span", "stage-time num", t));
      list.append(row);
    }
  }

  return {
    showUploading(name, frac) {
      show("jobCard", true);
      show("btnRerun", false);
      show("btnAlignScene", false);
      show("btnSafeRerun", false);
      show("btnStopRun", false);
      $("jobName").textContent = name;
      setBadge("uploading");
      show("queueBox", false);
      show("jobCamera", false);
      show("jobSamBatch", false);
      show("jobHamer", false);
      show("jobCorrection", false);
      $("jobMsg").textContent = `正在导入 ${Math.round(frac * 100)}%`;
      show("jobError", false);
    },
    render(job) {
      show("jobCard", true);
      show("btnRerun", ["done", "failed", "cancelled", "needs_alignment"].includes(job.status));
      show("btnAlignScene", !!job.scene_needs_build);
      show("btnSafeRerun", ["failed", "cancelled"].includes(job.status) && !job.params.static_camera);
      const stop = $("btnStopRun");
      show(stop, ["queued", "running", "waiting_user", "cancel_requested"].includes(job.status));
      stop.disabled = job.status === "cancel_requested";
      stop.textContent = job.status === "cancel_requested" ? "正在停止…" : "停止";
      $("jobName").textContent = jobLabel(job);
      $("jobId").textContent = job.id;
      setBadge(job.status);
      const queued = job.status === "queued";
      show("queueBox", queued);
      if (queued) {
        $("queueText").textContent = job.queue_position > 0
          ? `前面还有 ${job.queue_position} 个任务` : "即将开始";
      }
      renderStages(job.stages, job.now);
      let msg = MESSAGES[job.message] || job.message || "";
      msg = msg.replace(/^SAM: (\d+)\/(\d+) frames$/, "SAM 特征提取 · $1 / $2 帧");
      if (job.status === "waiting_user") msg = "请在视频编辑器中勾选要生成的人物";
      if (job.status === "done") {
        const total = job.finished && job.started ? ` · ${formatSeconds(job.finished - job.started)}` : "";
        const range = job.track_range ? ` · 素材第 ${job.track_range[0] + 1}–${job.track_range[1] + 1} 帧` : "";
        const people = job.person_count ? ` ${job.person_done}/${job.person_count} 人 · ` : " ";
        msg = `已生成${people}${job.num_frames} 帧${range}${total}`;
      } else if (job.current_person) {
        msg = `人物 ${job.current_person} · 已完成 ${job.person_done}/${job.person_count} 人 · ${msg}`;
      }
      $("jobMsg").textContent = msg;
      const camera = job.camera;
      const cameraInfo = !camera ? "" : camera.mode === "static" ? "相机 · 固定机位"
        : `相机 · ${camera.mode === "auto" ? "自动" : "手动"} · 采样 ${camera.samples}/${camera.frames} 帧 · 间隔 ${camera.interval}`;
      $("jobCamera").textContent = cameraInfo;
      show("jobCamera", !!cameraInfo);
      const batch = job.sam_batch;
      if (batch) {
        const actual = batch.actual == null ? "批次未记录" : `实际 ${batch.actual} 帧`;
        const memory = !batch.reused && batch.total_mib ? ` · 可用 ${(batch.free_mib / 1024).toFixed(1)} / ${(batch.total_mib / 1024).toFixed(1)} GiB` : "";
        $("jobSamBatch").textContent = `SAM · ${batch.reused ? "复用特征" : batch.requested == null ? "自动" : "手动"} · ${actual}${memory}${batch.retries && !batch.reused ? ` · 已降档 ${batch.retries} 次` : ""}`;
      }
      show("jobSamBatch", !!batch);
      const hamer = job.hamer_report;
      if (hamer) {
        const report = $("jobHamer");
        const sampling = hamer.stride > 1 ? `每 ${hamer.stride} 帧采样 · ` : hamer.stride === 1 ? "逐帧 · " : "";
        report.textContent = hamer.left || hamer.right
          ? `HaMeR · ${sampling}左手 ${hamer.left}/${hamer.frames} 帧 · 右手 ${hamer.right}/${hamer.frames} 帧 · ${formatSeconds(hamer.seconds)}`
          : "HaMeR · 无有效手框，已保留原手指动作";
        report.title = hamer.stride > 1
          ? `模型实际采样：左手 ${hamer.sampled_left} 帧，右手 ${hamer.sampled_right} 帧；其余有效帧由插值补齐。`
          : "";
      }
      show("jobHamer", !!hamer);
      const correction = job.correction;
      const correctionStatus = $("jobCorrection");
      const sole = correction?.sole_fit;
      const soleStatus = sole ? ` · 脚掌贴地 ${sole.strength ?? job.params?.sole_fit_strength ?? 0.6}${sole.adjusted ? "" : "（未调整）"}` : "";
      correctionStatus.textContent = correction
        ? `${correction.preset === "strong" ? "加强锁脚" : "标准锁脚"} · ${correction.automatic ? "自动" : "手动"}地面 ${correction.floor_m.toFixed(3)} m · ${correction.contacts ? formatSeconds(correction.seconds) : "未识别到可锁定的支撑"}${soleStatus}`
        : "";
      correctionStatus.title = correction?.warning || "";
      show(correctionStatus, !!correction);
      $("workspaceState").textContent = job.status === "running" ? `${job.progress}% · ${msg}`
        : job.status === "done" ? `${msg} · FlowHMR` : STATUS_LABEL[job.status] || job.status;
      $("jobError").textContent = job.error || "";
      show("jobError", job.status === "failed" && !!job.error);
    },
    showError(msg) {
      show("jobCard", true);
      show("btnRerun", false);
      show("btnAlignScene", false);
      show("btnSafeRerun", false);
      show("btnStopRun", false);
      show("jobCamera", false);
      show("jobSamBatch", false);
      show("jobHamer", false);
      show("jobCorrection", false);
      setBadge("failed");
      $("jobError").textContent = msg;
      show("jobError", true);
    },
    showActionError(msg) {
      show("jobCard", true);
      $("jobError").textContent = msg;
      show("jobError", true);
    },
  };

  function setBadge(status) {
    const b = $("jobBadge");
    b.textContent = STATUS_LABEL[status] || status;
    b.className = `badge ${status}`;
  }
}
