import { apiFetch } from "./api.js";
import { showToast, getCookie, safeStringify, formatDateTime, escapeHtml } from "./utils.js";
import { logsState } from "./state.js";

let isSendingFrontendLog = false;

export const sendFrontendLog = async ({ message, details, level = "ERRO" }) => {
  if (isSendingFrontendLog) return;
  isSendingFrontendLog = true;
  try {
    const csrfToken = getCookie("csrftoken");
    await fetch("/api/log-error/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      },
      body: JSON.stringify({
        message,
        details,
        level,
      }),
    });
  } catch (error) {
    console.error("Falha ao enviar log do frontend:", error);
  } finally {
    isSendingFrontendLog = false;
  }
};

window.addEventListener("error", (event) => {
  const message = event?.message || "Erro de JavaScript";
  const details =
    event?.error?.stack ||
    `${event?.filename || "arquivo desconhecido"}:${event?.lineno || 0}:${event?.colno || 0}`;
  sendFrontendLog({ message, details });
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event?.reason;
  const message = reason?.message || "Promise rejeitada sem tratamento";
  const details = reason?.stack || safeStringify(reason);
  sendFrontendLog({ message, details });
});

export const updateLogsPendingBadge = async () => {
  const badges = document.querySelectorAll(".logs-pending-badge");
  if (!badges.length) return;
  try {
    const data = await apiFetch("/api/logs/pending-count/");
    badges.forEach((badge) => {
      if (data.pending > 0) {
        badge.textContent = data.pending;
        badge.classList.remove("d-none");
      } else {
        badge.classList.add("d-none");
      }
    });
  } catch (error) {
    console.error("Erro ao carregar badge de logs:", error);
  }
};

export const renderSystemLogs = () => {
  const tableBody = document.getElementById("systemLogsTableBody");
  const emptyState = document.getElementById("systemLogsEmpty");
  if (!tableBody) return;

  if (!logsState.items.length) {
    tableBody.innerHTML = "";
    if (emptyState) emptyState.classList.remove("d-none");
    return;
  }

  if (emptyState) emptyState.classList.add("d-none");

  tableBody.innerHTML = logsState.items
    .map((log) => {
      const detailId = `logDetails-${log.id}`;
      const statusBadge = log.is_resolved
        ? '<span class="badge bg-success">Resolvido</span>'
        : '<span class="badge bg-danger">Pendente</span>';
      const resolveButton = log.is_resolved
        ? `<button class="btn btn-sm btn-outline-success" data-action="resolve" data-log-id="${log.id}" disabled>
            <i class="bi bi-check-circle me-1"></i>Resolvido
          </button>`
        : `<button class="btn btn-sm btn-success" data-action="resolve" data-log-id="${log.id}">
            <i class="bi bi-check2-circle me-1"></i>Marcar como Resolvido
          </button>`;

      return `
        <tr class="log-row" data-detail-id="${detailId}">
          <td>${formatDateTime(log.created_at)}</td>
          <td>${escapeHtml(log.source_label || log.source)}</td>
          <td>${escapeHtml(log.message)}</td>
          <td>${statusBadge}</td>
          <td class="text-end">
            <div class="btn-group btn-group-sm" role="group">
              <button class="btn btn-outline-secondary" data-action="copy" data-log-id="${log.id}">
                <i class="bi bi-clipboard"></i>
                Copiar Erro
              </button>
              ${resolveButton}
              <button class="btn btn-outline-danger" data-action="delete" data-log-id="${log.id}">
                <i class="bi bi-trash"></i>
                Excluir
              </button>
            </div>
          </td>
        </tr>
        <tr class="collapse bg-light" id="${detailId}">
          <td colspan="5">
            <div class="p-3">
              <p class="text-muted small mb-2">Traceback / Detalhes</p>
              <pre class="mb-0 small">${escapeHtml(log.details || "-")}</pre>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
};

export const loadSystemLogs = async () => {
  try {
    logsState.items = await apiFetch("/api/system-logs/");
    renderSystemLogs();
  } catch (error) {
    showToast(`Erro ao carregar logs: ${error.message}`, "danger");
  }
};

const copyLogDetails = async (details) => {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(details);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = details;
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
};

const handleSystemLogsTableClick = async (event) => {
  const actionButton = event.target.closest("button[data-action]");
  if (actionButton) {
    const action = actionButton.dataset.action;
    const logId = Number(actionButton.dataset.logId);
    const log = logsState.items.find((item) => item.id === logId);
    if (!log) return;

    if (action === "copy") {
      try {
        await copyLogDetails(log.details || "");
        showToast("Erro copiado para a área de transferência.", "success");
      } catch (error) {
        showToast("Não foi possível copiar o erro.", "danger");
      }
      return;
    }

    if (action === "resolve") {
      try {
        await apiFetch(`/api/system-logs/${logId}/`, {
          method: "PATCH",
          body: JSON.stringify({ is_resolved: true }),
        });
        log.is_resolved = true;
        renderSystemLogs();
        updateLogsPendingBadge();
        showToast("Log marcado como resolvido.", "success");
      } catch (error) {
        showToast(`Erro ao atualizar log: ${error.message}`, "danger");
      }
      return;
    }

    if (action === "delete") {
      if (!confirm("Deseja realmente excluir este log?")) return;
      try {
        await apiFetch(`/api/system-logs/${logId}/`, { method: "DELETE" });
        logsState.items = logsState.items.filter((item) => item.id !== logId);
        renderSystemLogs();
        updateLogsPendingBadge();
        showToast("Log removido.", "success");
      } catch (error) {
        showToast(`Erro ao excluir log: ${error.message}`, "danger");
      }
      return;
    }
  }

  const row = event.target.closest("tr.log-row");
  if (row) {
    const detailId = row.dataset.detailId;
    const target = document.getElementById(detailId);
    if (target) {
      const collapse = bootstrap.Collapse.getOrCreateInstance(target, { toggle: false });
      collapse.toggle();
    }
  }
};

export const initSystemLogs = () => {
  const tableBody = document.getElementById("systemLogsTableBody");
  if (!tableBody) return;
  tableBody.addEventListener("click", handleSystemLogsTableClick);
  loadSystemLogs();
};
