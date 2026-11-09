// Job history. Keep each row and its thumbnail mounted while progress changes.
import { $, show, el, formatRelative, STATUS_LABEL, jobLabel } from "./utils.js";
import * as api from "./api.js";

const ACTIVE = new Set(["queued", "running", "waiting_user", "cancel_requested", "uploading"]);
const STOP = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>';
const RERUN = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 9.4h5M3 19.6v-5h5m-5 5l3-3a8.2 8.2 0 0014-3.7M4 9.9a8.2 8.2 0 0113.8-3.7L21 9.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';

export function initHistory({ onOpen, onRerun, onDeleted }) {
  const list = $("historyList");
  const deleteSelected = $("historyDeleteSelected"), deleteAll = $("historyDeleteAll");
  const selected = new Set(), rows = new Map();
  let current = null, busy = null, refreshVersion = 0, timer = null, hasActive = false;
  let deletable = 0;

  function updateActions() {
    $("historySelectedCount").textContent = selected.size;
    deleteSelected.disabled = busy !== null || selected.size === 0;
    deleteAll.disabled = busy !== null || deletable === 0;
  }

  function setError(msg) {
    $("historyError").textContent = msg;
    show("historyError", !!msg);
  }

  function createRow(job) {
    const row = el("div", "run"), check = el("input", "run-select"), open = el("button", "run-open");
    const thumb = el("span", "run-thumb"), image = el("img"), info = el("div", "run-info");
    const name = el("div", "run-name", job.filename), sub = el("div", "run-sub");
    const tag = el("span", "badge"), action = el("button", "icon-btn");
    const { id } = job;
    const entry = { row, check, open, image, name, sub, tag, action, status: null, active: null, person: undefined, failedThumb: false };
    row.dataset.job = id;
    check.type = "checkbox";
    check.addEventListener("change", () => {
      if (check.checked) selected.add(id); else selected.delete(id);
      updateActions();
    });
    open.type = action.type = "button";
    open.addEventListener("click", () => onOpen(id));
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    image.addEventListener("load", () => { entry.failedThumb = false; thumb.classList.add("ready"); });
    image.addEventListener("error", () => { entry.failedThumb = true; thumb.classList.remove("ready"); });
    action.addEventListener("click", async () => {
      if (busy !== null) return;
      const stopping = entry.active;
      busy = stopping ? `stop:${id}` : id;
      setError("");
      void refresh();
      try { await (stopping ? api.cancelJob(id) : onRerun(id)); }
      catch (err) { setError(err.message || (stopping ? "停止任务失败" : "重跑失败")); }
      finally { busy = null; void refresh(); }
    });
    info.append(name, sub);
    thumb.append(image);
    open.append(thumb, info, tag);
    row.append(check, open, action);
    rows.set(id, entry);
    return entry;
  }

  function updateRow(entry, job, now) {
    const { row, check, open, image, name, sub, tag, action } = entry;
    const active = ACTIVE.has(job.status);
    const person = job.selected_person ?? null;
    if (entry.person !== person || (entry.status !== job.status && entry.failedThumb)) {
      entry.person = person;
      image.src = `${api.thumbnailUrl(job.id)}?person=${person ?? ""}&stage=${job.status}`;
    }
    const label = jobLabel(job);
    name.textContent = open.title = label;
    check.setAttribute("aria-label", `选中 ${label} 以删除`);
    if (entry.active !== active) action.innerHTML = active ? STOP : RERUN;
    entry.status = job.status;
    entry.active = active;
    row.classList.toggle("current", job.id === current);
    check.checked = selected.has(job.id);
    check.disabled = active || busy !== null;
    const correction = job.params.postprocess
      ? ` · ${job.params.correction_preset === "strong" ? "加强锁脚" : "标准锁脚"} · ${job.params.correction_floor_m == null ? "自动" : "手动"}地面` : "";
    sub.textContent = job.recovered ? "从磁盘恢复" : `${formatRelative(job.created, now)}${correction} · CFG ${job.params.cfg_scale} · ${job.params.steps} 步`;
    sub.title = sub.textContent;
    tag.className = `badge ${job.status}`;
    tag.textContent = job.status === "running" ? `${job.progress}%` : STATUS_LABEL[job.status] || job.status;
    action.title = active ? (job.status === "cancel_requested" ? "正在停止" : "停止这次任务") : "用当前设置重跑";
    action.setAttribute("aria-label", `${action.title}: ${label}`);
    action.disabled = busy !== null || job.status === "cancel_requested";
    action.classList.toggle("spin", busy === job.id);
  }

  async function refresh() {
    clearTimeout(timer);
    const version = ++refreshVersion;
    let data;
    try { data = await api.getJobs(); } catch {
      if (version === refreshVersion && hasActive) timer = setTimeout(refresh, 3000);
      return;
    }
    const { jobs, now } = data;
    if (version !== refreshVersion) return jobs;
    hasActive = jobs.some((job) => ACTIVE.has(job.status));
    if (hasActive) timer = setTimeout(refresh, 2000);
    const visible = new Set(jobs.map((job) => job.id));
    for (const id of selected) if (!visible.has(id)) selected.delete(id);
    for (const [id, entry] of rows) {
      if (!visible.has(id)) { entry.row.remove(); rows.delete(id); }
    }
    deletable = data.deletable_count;
    $("historySummary").textContent = jobs.length ? `· ${jobs.length} 条` : "";
    show("historyEmpty", jobs.length === 0);
    jobs.forEach((job, i) => {
      const entry = rows.get(job.id) ?? createRow(job);
      updateRow(entry, job, now);
      if (list.children[i] !== entry.row) list.insertBefore(entry.row, list.children[i] ?? null);
    });
    updateActions();
    return jobs;
  }

  $("historyRefresh").addEventListener("click", refresh);
  deleteSelected.addEventListener("click", async () => {
    const ids = [...selected];
    if (ids.length && window.confirm(`删除选中的 ${ids.length} 条任务及其文件？`)) await removeRuns(ids);
  });
  deleteAll.addEventListener("click", async () => {
    if (window.confirm("删除所有已结束的任务及其文件？正在处理的任务会保留。")) await removeRuns();
  });

  async function removeRuns(ids) {
    setError("");
    busy = "delete";
    updateActions();
    try {
      const result = await api.deleteJobs(ids);
      selected.clear();
      if (result.skipped.length) setError(`已删除 ${result.deleted.length} 条，${result.skipped.length} 条未删除。`);
      onDeleted(result.deleted);
    } catch (err) { setError(err.message || "删除任务失败"); }
    finally { busy = null; await refresh(); }
  }

  return { refresh, setCurrent(id) {
    current = id;
    for (const [jobId, entry] of rows) entry.row.classList.toggle("current", jobId === id);
  } };
}
