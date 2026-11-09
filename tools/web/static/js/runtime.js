import { $, el, show } from "./utils.js";
import { getRuntime, selectRuntime, startRuntimeDownload, stopRuntimeDownload } from "./api.js";

const PHASES = { download: "正在下载", verify: "正在校验", install: "正在解包", test: "正在验证 GPU" };
const GB = (value) => `${(value / 1e9).toFixed(2)} GB`;
const active = (transfer) => ["running", "stopping"].includes(transfer?.status);
const REOPEN = "flowhmr-runtime-reopen";

export function initRuntimeDialog() {
  const button = $("btnRuntime"), dialog = $("runtimeDialog"), list = $("runtimeList");
  const status = $("runtimeCheckStatus"), directory = $("runtimeDirectory"), folder = $("runtimeOpenFolder");
  const stop = $("runtimeDownloadStop"), restart = $("runtimeRestart"), refresh = $("runtimeRefresh");
  const transferBox = $("runtimeTransfer"), transferBar = $("runtimeTransferBar");
  let state = null, busy = false, timer = null, generation = 0;

  function summarize(next) {
    show(button, !!next?.supported);
    button.classList.toggle("needs-models", next?.supported && !next.ready);
    $("runtimeInfo").textContent = next?.pending_restart ? "待切换" : next?.label ?? "未启用";
  }

  function render() {
    if (!state) return;
    const transfer = state.download;
    const running = active(transfer);
    summarize(state);
    directory.value = state.directory;
    folder.disabled = !state.directory;
    $("runtimeGpu").textContent = state.gpu ? `${state.gpu.name} · 驱动 ${state.gpu.driver}`
      : "未读取到 NVIDIA 显卡信息。启用前会实际验证 GPU。";
    list.replaceChildren(...state.options.map((option) => {
      const item = el("div", "model-item runtime-option");
      item.dataset.version = option.id;
      const info = el("div", "runtime-option-info");
      const title = el("div", "runtime-option-title");
      const isActive = option.id === state.active;
      const pending = state.pending_restart && option.id === state.selected;
      const label = isActive ? "使用中" : pending ? "待切换" : option.installed ? "已安装" : "未安装";
      const badge = el("span", "model-badge", label);
      badge.dataset.state = option.installed ? "ready" : "missing";
      title.append(el("strong", "", option.label), badge);
      if (option.recommended) title.append(el("span", "runtime-recommended", "推荐"));
      info.append(title, el("p", "model-issue", option.detail + (option.bytes ? ` · 下载 ${GB(option.bytes)}` : "")));
      if (option.source && !option.installed) {
        const link = el("a", "runtime-source", "PyTorch 官方");
        link.href = option.source;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        info.append(link);
      }
      const action = el("button", option.recommended && !option.installed ? "btn-primary small" : "btn-secondary small",
        option.installed ? "启用" : transfer?.version === option.id && transfer.status === "cancelled" ? "继续下载" : "下载");
      action.type = "button";
      action.disabled = busy || running || isActive || pending || !option.compatible || (!option.installed && state.pending_restart);
      action.addEventListener("click", () => transact(async () => {
        if (option.installed) {
          Object.assign(state, await selectRuntime(option.id));
          if (state.pending_restart) await applySwitch();
        } else state.download = await startRuntimeDownload(option.id);
      }));
      item.append(info, action);
      return item;
    }));
    show(stop, running);
    stop.disabled = busy || transfer?.status === "stopping";
    show(restart, state.pending_restart && !!window.pywebview?.api?.restart_runtime);
    restart.disabled = busy;
    refresh.disabled = busy;
    show(transferBox, !!transfer && transfer.status !== "idle");
    show(transferBar, running);
    if (running && transfer.total > 0) {
      transferBar.max = transfer.total;
      transferBar.value = transfer.bytes;
    } else transferBar.removeAttribute("value");
    const target = state.options.find((option) => option.id === transfer?.version)?.label ?? "";
    $("runtimeTransferLabel").textContent = running
      ? [transfer.status === "stopping" ? "正在停止…" : PHASES[transfer.phase], target,
          transfer.total > 0 ? `${GB(transfer.bytes)} / ${GB(transfer.total)}` : ""].filter(Boolean).join(" · ")
      : transfer?.status === "failed" ? transfer.error
        : transfer?.status === "cancelled" ? "已停止，下次可继续下载。"
          : transfer?.status === "done" ? `${target} 已通过验证，点击「启用」使用。` : "";
    status.textContent = state.pending_restart ? "重启推理服务后生效。"
      : state.ready ? `${state.label} 使用中` : "请选择一个运行环境。";
  }

  async function applySwitch() {
    const apply = window.pywebview?.api?.restart_runtime;
    if (!apply) return;
    sessionStorage.setItem(REOPEN, "1");
    if (!await apply()) {
      sessionStorage.removeItem(REOPEN);
      throw new Error("未能重启服务，请点击「应用切换」重试。");
    }
  }

  function poll() {
    clearTimeout(timer);
    if (dialog.open && !busy && active(state?.download)) timer = setTimeout(load, 800);
  }

  async function load() {
    const token = ++generation;
    try {
      const next = await getRuntime();
      if (token !== generation || !dialog.open) return;
      state = next;
      render();
    } catch (error) {
      if (token === generation) status.textContent = error.message;
    }
    if (token === generation) poll();
  }

  async function transact(action) {
    if (busy) return;
    busy = true;
    generation++;
    clearTimeout(timer);
    render();
    let problem;
    try { await action(); }
    catch (error) { problem = error.message; }
    finally { busy = false; render(); poll(); }
    if (problem) status.textContent = problem;
  }

  function open() {
    if (dialog.open) return;
    dialog.showModal();
    void load();
  }
  button.addEventListener("click", open);
  refresh.addEventListener("click", load);
  dialog.addEventListener("close", () => { generation++; clearTimeout(timer); });
  stop.addEventListener("click", () => transact(async () => { state.download = await stopRuntimeDownload(state.download.id); }));
  restart.addEventListener("click", () => transact(applySwitch));
  folder.addEventListener("click", async () => {
    if (window.pywebview?.api?.open_runtime_folder) await window.pywebview.api.open_runtime_folder();
    else { directory.focus(); directory.select(); }
  });
  return { summarize, open, restore: () => {
    if (sessionStorage.getItem(REOPEN)) { sessionStorage.removeItem(REOPEN); open(); }
  } };
}
