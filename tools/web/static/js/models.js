import { $, el, formatBytes, show } from "./utils.js";
import { getModelDownload, startModelDownload, stopModelDownload } from "./api.js";

const LABELS = { ready: "已就绪", missing: "缺文件", unavailable: "未就绪" };
const PHASES = { download: "下载", verify: "校验", install: "安装" };
const active = (state) => state?.status === "running" || state?.status === "stopping";
const sizeLabel = (n) => n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(2)} GB` : formatBytes(n);

export function initModelDialog(refreshInventory) {
  const dialog = $("modelDialog"), list = $("modelList");
  const directory = $("modelDirectory"), folderButton = $("modelOpenFolder");
  const refreshButton = $("modelRefresh"), status = $("modelCheckStatus");
  const downloadButton = $("modelDownload"), stopButton = $("modelDownloadStop");
  const transferBox = $("modelTransfer"), transferLabel = $("modelTransferLabel");
  const transferBar = $("modelTransferBar"), transferErrors = $("modelTransferErrors");
  let inventory = null, transfer = null, busy = false, pollTimer = null, version = 0;

  function render(next) {
    inventory = next;
    directory.value = inventory.directory;
    folderButton.disabled = false;
    list.replaceChildren(...inventory.items.map((item) => {
      const row = el("div", "model-item");
      row.dataset.model = item.id;
      const heading = el("div", "model-row");
      const badge = el("span", "model-badge", LABELS[item.status]);
      badge.dataset.state = item.status;
      heading.append(el("strong", "", item.name), badge);
      row.append(heading);
      if (item.status !== "ready") {
        const help = el("div", "model-install");
        if (item.status === "missing") help.append(el("code", "", item.folder));
        for (const { label, url } of item.links) {
          const link = el("a", "", label);
          link.href = url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          help.append(link);
        }
        row.append(help);
        if (item.issue) row.append(el("p", "model-issue", item.issue));
      }
      return row;
    }));
    const missing = inventory.items.filter((item) => item.blocking).length;
    status.textContent = missing ? `缺少 ${missing} 组必需模型` : "必需模型齐全";
  }

  const groupName = (group) => inventory?.items.find((item) => item.id === group)?.name ?? group;

  function renderTransfer() {
    const running = active(transfer);
    show(downloadButton, !running && !!inventory?.downloadable?.length);
    show(stopButton, running);
    downloadButton.disabled = busy;
    stopButton.disabled = busy || transfer?.status === "stopping";
    downloadButton.textContent = transfer?.status === "cancelled" ? "继续下载" : "下载缺失模型";
    downloadButton.title = inventory?.download_bytes ? `最多下载 ${sizeLabel(inventory.download_bytes)}` : "";
    show(transferBox, transfer && transfer.status !== "idle");
    show(transferBar, running);
    const errors = transfer?.errors ?? [];
    show(transferErrors, errors.length > 0);
    transferErrors.replaceChildren(...errors.map((error) =>
      el("li", "", `${groupName(error.group)}${error.file ? ` · ${error.file}` : ""}：${error.message}`)));
    if (running) {
      const parts = [transfer.status === "stopping" ? "正在停止…" : PHASES[transfer.phase]];
      if (transfer.group) parts.push(`${groupName(transfer.group)}（${transfer.index}/${transfer.count}）`);
      if (transfer.file) parts.push(transfer.file);
      if (transfer.total > 0) {
        transferBar.max = transfer.total;
        transferBar.value = transfer.bytes;
        parts.push(`${sizeLabel(transfer.bytes)} / ${sizeLabel(transfer.total)}`);
      } else transferBar.removeAttribute("value");
      transferLabel.textContent = parts.join(" · ");
    } else {
      transferLabel.textContent = transfer?.status === "cancelled" ? "下载已停止，下次可从断点继续。"
        : errors.length ? "有模型未能安装，可重试下载或使用链接。" : "下载完成，文件已放入模型目录。";
    }
  }

  function schedulePoll() {
    clearTimeout(pollTimer);
    if (dialog.open && !busy && active(transfer)) pollTimer = setTimeout(pollDownload, 700);
  }

  async function pollDownload() {
    const token = version;
    try {
      const next = await getModelDownload();
      if (token !== version || !dialog.open) return;
      transfer = next;
      renderTransfer();
      if (!active(transfer)) { await refresh(); return; }
    } catch {
      if (token !== version || !dialog.open) return;
      transferLabel.textContent = "正在重新连接下载服务…";
    }
    schedulePoll();
  }

  async function refresh() {
    if (busy) return;
    busy = true;
    version++;
    clearTimeout(pollTimer);
    refreshButton.disabled = true;
    renderTransfer();
    list.setAttribute("aria-busy", "true");
    status.textContent = "正在检查模型文件…";
    try {
      const next = await refreshInventory();
      render(next);
      transfer = next.download ?? null;
    } catch (error) {
      status.textContent = `检查失败：${error.message}`;
    } finally {
      busy = false;
      refreshButton.disabled = false;
      list.removeAttribute("aria-busy");
      renderTransfer();
      schedulePoll();
    }
  }

  async function changeDownload(action) {
    if (busy) return;
    busy = true;
    version++;
    clearTimeout(pollTimer);
    renderTransfer();
    let updated = false;
    try {
      transfer = await action();
      updated = true;
    } catch (error) {
      status.textContent = error.message;
    } finally {
      busy = false;
      renderTransfer();
      schedulePoll();
    }
    if (updated && !active(transfer)) void refresh();
  }

  function syncFolderButton() {
    folderButton.textContent = window.pywebview?.api?.open_models_folder ? "打开文件夹" : "复制路径";
  }
  window.addEventListener("pywebviewready", syncFolderButton);
  $("btnModels").addEventListener("click", () => {
    syncFolderButton();
    dialog.showModal();
    void refresh();
  });
  refreshButton.addEventListener("click", refresh);
  downloadButton.addEventListener("click", () => changeDownload(startModelDownload));
  stopButton.addEventListener("click", () => changeDownload(() => stopModelDownload(transfer.id)));
  dialog.addEventListener("close", () => { version++; clearTimeout(pollTimer); });
  folderButton.addEventListener("click", async () => {
    try {
      if (window.pywebview?.api?.open_models_folder) await window.pywebview.api.open_models_folder();
      else {
        await navigator.clipboard.writeText(directory.value);
        status.textContent = "已复制模型文件夹路径。";
      }
    } catch {
      directory.select();
      status.textContent = "可按 Ctrl+C 复制模型文件夹路径。";
    }
  });
}
