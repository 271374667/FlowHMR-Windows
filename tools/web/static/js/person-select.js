// Person selection card.
//  - choosing: one row per detected person (thumbnail, colour matching its box in the video
//    preview, frame count); toggle any rows or video boxes, then confirm together.
//  - locked:   each queued or finished job shows its own selected person.
import { $, show, el, personColor } from "./utils.js";
import * as api from "./api.js";

const CHECK_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';

export function initPersonSelect(bus) {
  let jobId = null;
  let candidates = [];
  let defaultIdx = null;
  let previewIndex = null, lockedIndex = null;
  const selected = new Set();
  let rows = [];
  let mode = "hidden";      // "hidden" | "choosing" | "locked"
  let submitting = false, confirmed = false;

  const list = $("personList");

  function thumb(i, cls) {
    const box = el("span", cls);
    box.style.borderColor = personColor(i);
    const img = el("img");
    img.alt = `人物 ${i + 1}`;
    img.loading = "lazy";
    img.src = api.personThumbUrl(jobId, i);
    img.onerror = () => { img.remove(); box.classList.add("no-img"); box.textContent = `${i + 1}`; };
    box.append(img);
    return box;
  }

  function renderChoosing() {
    list.innerHTML = "";
    rows = candidates.map((c, i) => {
      const btn = el("button", "person");
      btn.type = "button";
      btn.append(thumb(i, "person-thumb"));
      const text = el("span", "person-text");
      const name = el("span", "person-name");
      const chip = el("span", "person-dot");
      const tag = el("span", "person-tag");
      chip.style.background = personColor(i);
      name.append(chip, document.createTextNode(`人物 ${i + 1}`), tag);
      text.append(name, el("span", "person-meta num",
        `${c.num_frames} 帧 · ${(c.num_frames / 30).toFixed(1)} 秒 · 第 ${c.start + 1}–${c.end + 1} 帧`));
      btn.append(text);
      const mark = el("span", "person-check");
      mark.innerHTML = CHECK_SVG;
      btn.append(mark);
      btn.addEventListener("click", () => togglePerson(i));
      list.append(btn);
      return { btn, tag };
    });
    syncChoosing();
  }

  function syncChoosing() {
    rows.forEach(({ btn, tag }, i) => {
      const checked = selected.has(i);
      btn.classList.toggle("selected", checked);
      btn.setAttribute("aria-pressed", String(checked));
      btn.disabled = submitting || confirmed;
      tag.textContent = i === previewIndex ? "正在预览" : i === defaultIdx ? "建议" : "";
      show(tag, !!tag.textContent);
    });
    $("personCount").textContent = `检测到 ${candidates.length} 人，已选 ${selected.size} 人。点击缩略图或视频框可勾选，再点一次取消。`;
    const btn = $("personConfirm");
    btn.disabled = !selected.size || submitting || confirmed;
    btn.textContent = submitting ? "正在提交…" : confirmed ? "已确认，正在准备任务…"
      : !selected.size ? "请勾选人物" : selected.size === 1 ? `确认人物 ${selected.values().next().value + 1}`
      : `生成所选 ${selected.size} 人`;
  }

  function renderLocked(job, candidate) {
    list.innerHTML = "";
    const row = el("div", "person locked");
    row.append(thumb(lockedIndex, "person-thumb large"));
    const text = el("span", "person-text");
    const name = el("span", "person-name");
    const chip = el("span", "person-dot");
    chip.style.background = "#10b981";
    name.append(chip, document.createTextNode(`人物 ${lockedIndex + 1}`));
    const how = job.selection_auto ? "自动选取" : "手动选取";
    text.append(name, el("span", "person-meta", how));
    if (candidate) text.append(el("span", "person-meta num", `${candidate.num_frames} 帧 · 第 ${candidate.start + 1}–${candidate.end + 1} 帧`));
    row.append(text);
    list.append(row);
  }

  function togglePerson(i) {
    if (mode !== "choosing" || submitting || confirmed || !candidates[i]) return;
    if (selected.has(i)) selected.delete(i); else selected.add(i);
    previewIndex = i;
    syncChoosing();
    bus.emit("person:selection", { selected: [...selected], previewIndex });
  }

  $("personConfirm").addEventListener("click", async () => {
    if (!selected.size || !jobId || mode !== "choosing" || submitting || confirmed) return;
    const id = jobId;
    submitting = true;
    setError("");
    syncChoosing();
    try {
      const result = await api.selectPeople(id, [...selected]);
      if (jobId !== id) return;
      confirmed = true;
      bus.emit("person:confirmed", result.people ?? [...selected]);
    } catch (e) {
      if (jobId === id && mode === "choosing") setError(e.message || "选择人物失败");
    } finally {
      if (jobId === id) {
        submitting = false;
        if (mode === "choosing") syncChoosing();
      }
    }
  });

  function setError(msg) {
    $("personError").textContent = msg;
    show("personError", !!msg);
  }

  function setMode(m, job, candidate) {
    mode = m;
    const card = $("personCard");
    card.classList.toggle("attention", m === "choosing");
    $("personTitle").textContent = m === "locked" ? "正在重建人物" : "选择人物";
    show("personConfirm", m === "choosing");
    show("personCount", m === "choosing");
    if (m !== "locked") show("personReselect", false);
    show(card, m !== "hidden");
    if (m === "choosing") renderChoosing();
    else rows = [];
    if (m === "locked") renderLocked(job, candidate);
  }

  $("personReselect").addEventListener("click", () => bus.emit("person:reselect"));

  return {
    /** Called on every job poll. */
    update(job) {
      const cands = Array.isArray(job.candidates) ? job.candidates : [];
      const changedJob = jobId !== job.id;
      if (changedJob) {
        jobId = job.id;
        candidates = [];
        defaultIdx = previewIndex = lockedIndex = null;
        selected.clear();
        submitting = confirmed = false;
        setError("");
      }
      if (job.status === "waiting_user" && cands.length) {
        if (mode !== "choosing" || changedJob) {
          candidates = cands;
          previewIndex = defaultIdx = job.default_person ?? 0;
          setMode("choosing", job);
          bus.emit("person:candidates", { candidates, selected: [], previewIndex });
        }
      } else if (job.selected_person != null) {
        const changed = mode !== "locked" || lockedIndex !== job.selected_person;
        lockedIndex = job.selected_person;
        if (changed) {
          const candidate = candidates[lockedIndex] ?? cands[lockedIndex] ?? job.person_track;
          setError("");
          setMode("locked", job, candidate);
          bus.emit("person:locked", { candidate, index: lockedIndex });
          candidates = [];
        }
        $("personTitle").textContent = job.status === "done" ? "已重建人物"
          : job.status === "running" ? "正在重建人物" : "已选人物";
      } else if (mode !== "hidden") {
        setMode("hidden");
        bus.emit("person:candidates", { candidates: [], selected: [], previewIndex: null });
      }
      // Offer a re-pick once the job has finished (needs a re-run of detection).
      show("personReselect", mode === "locked" && ["done", "failed"].includes(job.status));
    },
    select: togglePerson,
    reset() {
      jobId = null; candidates = []; defaultIdx = previewIndex = lockedIndex = null;
      selected.clear();
      submitting = confirmed = false;
      setError("");
      setMode("hidden");
      bus.emit("person:candidates", { candidates: [], selected: [], previewIndex: null });
    },
  };
}
