const appState = {
  year: null,
  month: null,
  categories: [],
  importer: {
    pendingCategoryIndex: null,
  },
  data: {
    cards: [],
    purchases: [],
    recurring: [],
    totals: { total_month: 0, total_card: 0, total_recurring: 0 },
  },
  filters: {
    purchaseSearch: "",
    purchaseCard: "all",
    purchaseType: "all",
    purchaseSort: "date",
    recurringSearch: "",
    recurringSort: "date",
  },
};

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const monthNames = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

const PRIVACY_STORAGE_KEY = "financeiro:privacy-active";

const elements = {};
const chartState = {
  line: null,
  doughnut: null,
};

const initPrivacyToggle = () => {
  const body = document.body;
  if (!body) return;
  const toggleButton = document.getElementById("privacyToggle");
  const storedPreference = localStorage.getItem(PRIVACY_STORAGE_KEY);

  if (storedPreference === "true") {
    body.classList.add("privacy-active");
  }

  const syncButtonState = () => {
    if (!toggleButton) return;
    const isActive = body.classList.contains("privacy-active");
    toggleButton.setAttribute("aria-pressed", isActive ? "true" : "false");
    toggleButton.classList.toggle("btn-primary", isActive);
    toggleButton.classList.toggle("btn-outline-secondary", !isActive);
    toggleButton.innerHTML = `<i class="bi ${isActive ? "bi-eye-slash" : "bi-eye"}" aria-hidden="true"></i>`;
  };

  syncButtonState();

  if (!toggleButton) return;
  toggleButton.addEventListener("click", () => {
    body.classList.toggle("privacy-active");
    localStorage.setItem(PRIVACY_STORAGE_KEY, body.classList.contains("privacy-active"));
    syncButtonState();
  });
};

const getCookie = (name) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
};

const apiFetch = async (url, options = {}) => {
  const headers = options.headers || {};
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }
  const csrfToken = getCookie("csrftoken");
  if (csrfToken) {
    headers["X-CSRFToken"] = csrfToken;
  }

  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers,
  });

  if (!response.ok) {
    // CORREÇÃO: Lemos como texto puro primeiro para não travar o stream
    const textData = await response.text();
    let errorDetail = "";

    try {
      // Tentamos converter manualmente para JSON
      const data = JSON.parse(textData);
      errorDetail = data.error || data.detail || JSON.stringify(data);
    } catch (error) {
      // Se falhar (ex: é uma página HTML de erro 404 ou 500), usamos o texto ou o status
      // Cortamos o texto para não encher o alerta com HTML gigante
      errorDetail = `Erro ${response.status} no servidor.`;
      console.error("Conteúdo do erro não-JSON:", textData);
    }
    throw new Error(errorDetail);
  }

  return response.json();
};

const safeStringify = (value) => {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch (error) {
    return String(value);
  }
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

let isSendingFrontendLog = false;

const sendFrontendLog = async ({ message, details, level = "ERRO" }) => {
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

const showToast = (message, type = "success") => {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-bg-${type} border-0`;
  toast.role = "alert";
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>
    </div>
  `;
  container.appendChild(toast);
  const bsToast = new bootstrap.Toast(toast, { delay: 4000 });
  bsToast.show();
  toast.addEventListener("hidden.bs.toast", () => toast.remove());
};

const formatCurrency = (value) => currencyFormatter.format(Number(value || 0));

const formatDate = (dateStr) => {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleDateString("pt-BR");
};

const formatDateTime = (dateStr) => {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("pt-BR");
};

const setLoadingState = (isLoading) => {
  if (!isLoading) return;
  elements.purchaseTableBody.innerHTML = `<tr class="skeleton-row"><td colspan="7"><div class="skeleton-line"></div></td></tr>`;
  elements.recurringTableBody.innerHTML = `<tr class="skeleton-row"><td colspan="6"><div class="skeleton-line"></div></td></tr>`;
};

const populateMonthSelectors = () => {
  elements.monthSelect.innerHTML = monthNames
    .map(
      (name, index) =>
        `<option value="${index + 1}">${name}</option>`
    )
    .join("");
  const currentYear = new Date().getFullYear();
  const startYear = currentYear - 2;
  const endYear = currentYear + 2;
  elements.yearSelect.innerHTML = "";
  for (let year = startYear; year <= endYear; year += 1) {
    elements.yearSelect.insertAdjacentHTML(
      "beforeend",
      `<option value="${year}">${year}</option>`
    );
  }
};

const updateSelectors = () => {
  elements.monthSelect.value = appState.month;
  elements.yearSelect.value = appState.year;
};

// --- BLOCO 1: Função para carregar categorias ---
const loadCategories = async () => {
  try {
    const cats = await apiFetch('/api/categories/');
    appState.categories = cats;

    // 1. Preenche Select de Compras
    const selectPurchase = document.getElementById('purchaseCategory');
    if (selectPurchase) {
        selectPurchase.innerHTML = '<option value="">Sem categoria</option>';
        cats.forEach(c => selectPurchase.innerHTML += `<option value="${c.id}">${c.nome}</option>`);
    }

    // 2. Preenche Select de Recorrências (ESTA É A NOVIDADE)
    const selectRecurring = document.getElementById('recurringCategory');
    if (selectRecurring) {
        selectRecurring.innerHTML = '<option value="">Sem categoria</option>';
        cats.forEach(c => selectRecurring.innerHTML += `<option value="${c.id}">${c.nome}</option>`);
    }
  } catch (e) {
    console.error("Erro ao carregar categorias:", e);
  }
};

const appendCategoryOption = (select, category) => {
  if (!select) return;
  const option = document.createElement("option");
  option.value = category.id;
  option.textContent = category.nome;
  select.appendChild(option);
};

const updateImportCategorySelects = (category, selectedIndex = null) => {
  const selects = document.querySelectorAll('#importTableBody select[id^="imp-cat-"]');
  selects.forEach((select) => {
    appendCategoryOption(select, category);
    if (selectedIndex !== null && select.id === `imp-cat-${selectedIndex}`) {
      select.value = String(category.id);
    }
  });
};

const handleCategorySubmit = async (event) => {
  event.preventDefault();
  const form = event.target;
  const nameInput = document.getElementById("categoryName");
  const nome = nameInput?.value.trim();
  if (!nome) {
    showToast("Informe o nome da categoria.", "danger");
    return;
  }

  try {
    const category = await apiFetch("/api/categories/", {
      method: "POST",
      body: JSON.stringify({ nome }),
    });
    appState.categories = [...(appState.categories || []), category];

    appendCategoryOption(document.getElementById("purchaseCategory"), category);
    appendCategoryOption(document.getElementById("recurringCategory"), category);

    const importModal = document.getElementById("importModal");
    if (importModal?.classList.contains("show")) {
      const selectedIndex = appState.importer?.pendingCategoryIndex;
      updateImportCategorySelects(category, selectedIndex ?? null);
    }
    appState.importer.pendingCategoryIndex = null;

    form.reset();
    bootstrap.Modal.getInstance(document.getElementById("categoryModal"))?.hide();
    showToast("Categoria criada com sucesso.", "success");
  } catch (error) {
    showToast(`Erro ao criar categoria: ${error.message}`, "danger");
  }
};

let importedItems = [];
let refreshDashboardCallback = null;

const initImporter = (refreshCallback) => {
  refreshDashboardCallback = refreshCallback;

  const btnAnalyze = document.getElementById("btnAnalyzeImport");
  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", analyzeImportText);
  }

  const btnSave = document.getElementById("btnSaveImport");
  if (btnSave) {
    btnSave.addEventListener("click", saveImportBatch);
  }

  const btnReset = document.getElementById("btnResetImport");
  if (btnReset) {
    btnReset.addEventListener("click", resetImportModal);
  }
};

const analyzeImportText = async () => {
  const textInput = document.getElementById("importText");
  const text = textInput?.value || "";

  if (!text.trim()) {
    alert("Cole algum texto da fatura primeiro.");
    return;
  }

  document.getElementById("stepPaste")?.classList.add("d-none");
  document.getElementById("importLoading")?.classList.remove("d-none");

  try {
    const data = await apiFetch("/api/import/parse/", {
      method: "POST",
      body: JSON.stringify({ text }),
    });

    importedItems = data;
    await renderImportTable();

    const cardSelect = document.getElementById("importCardSelect");
    if (cardSelect) {
      cardSelect.innerHTML = '<option value="">Selecione o Cartão...</option>';
      appState.data.cards.forEach((card) => {
        cardSelect.innerHTML += `<option value="${card.id}">${card.nome}</option>`;
      });
    }

    document.getElementById("importLoading")?.classList.add("d-none");
    document.getElementById("stepReview")?.classList.remove("d-none");
  } catch (error) {
    showToast(`Erro na análise: ${error.message}`, "danger");
    resetImportModal();
  }
};

const renderImportTable = async () => {
  const tbody = document.getElementById("importTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  let categories = appState.categories || [];
  if (!categories.length) {
    categories = await apiFetch("/api/categories/");
    appState.categories = categories;
  }
  const catOptions = categories
    .map((category) => `<option value="${category.id}">${category.nome}</option>`)
    .join("");

  importedItems.forEach((item, index) => {
    const tr = document.createElement("tr");
    if (item.is_duplicate) {
      tr.classList.add("table-danger");
    }

    let badgeClass = "bg-secondary";
    if (item.tipo_compra === "Online") badgeClass = "bg-info";
    if (item.tipo_compra === "Física") badgeClass = "bg-warning text-dark";

    const duplicateBadge = item.is_duplicate
      ? '<span class="badge bg-danger ms-1" style="font-size:0.7em">Duplicada</span>'
      : "";

    tr.innerHTML = `
      <td><input type="date" class="form-control form-control-sm" value="${item.data}" id="imp-date-${index}"></td>
      <td>
        <input type="text" class="form-control form-control-sm mb-1" value="${item.descricao}" id="imp-desc-${index}">
        <span class="badge ${badgeClass}" style="font-size:0.7em">${item.tipo_compra || "?"}</span>
        ${duplicateBadge}
      </td>
      <td>
        <span class="badge bg-light text-dark border">x${item.parcelas}</span>
      </td>
      <td>
        <input type="number" step="0.01" class="form-control form-control-sm" value="${item.valor}" id="imp-val-${index}">
      </td>
      <td>
        <div class="d-flex gap-1 align-items-center">
          <select class="form-select form-select-sm" id="imp-cat-${index}">
            <option value="">Sem Categoria</option>
            ${catOptions}
          </select>
          <button type="button" class="btn btn-outline-primary btn-sm add-cat-btn" data-index="${index}">
            +
          </button>
        </div>
      </td>
      <td class="text-end">
        <button class="btn btn-sm text-danger btn-remove-item" data-index="${index}">
          <i class="bi bi-x-lg"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);

    if (item.category_id) {
      const select = document.getElementById(`imp-cat-${index}`);
      if (select) select.value = item.category_id;
    }
  });

  document.querySelectorAll(".add-cat-btn").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const idx = Number(event.currentTarget.dataset.index);
      appState.importer.pendingCategoryIndex = idx;
      const modalElement = document.getElementById("categoryModal");
      if (modalElement) {
        bootstrap.Modal.getOrCreateInstance(modalElement).show();
      }
    });
  });

  document.querySelectorAll(".btn-remove-item").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const idx = event.target.closest("button").dataset.index;
      removeImportItem(Number(idx));
    });
  });
};

const removeImportItem = (index) => {
  importedItems.splice(index, 1);
  renderImportTable();
};

const saveImportBatch = async () => {
  const cardId = document.getElementById("importCardSelect")?.value;
  if (!cardId) {
    alert("Por favor, selecione o cartão.");
    return;
  }

  const finalItems = importedItems.map((item, index) => ({
    data: document.getElementById(`imp-date-${index}`)?.value,
    descricao: document.getElementById(`imp-desc-${index}`)?.value,
    valor: parseFloat(document.getElementById(`imp-val-${index}`)?.value),
    parcelas: item.parcelas,
    category_id: document.getElementById(`imp-cat-${index}`)?.value,
  }));

  setLoadingState(true);
  try {
    const result = await apiFetch("/api/import/save/", {
      method: "POST",
      body: JSON.stringify({
        card_id: cardId,
        items: finalItems,
      }),
    });

    showToast(`${result.count} compras importadas!`);

    const modalEl = document.getElementById("importModal");
    if (modalEl) {
      const modal = bootstrap.Modal.getInstance(modalEl);
      modal?.hide();
    }

    resetImportModal();

    if (refreshDashboardCallback) refreshDashboardCallback();
  } catch (error) {
    showToast(`Erro ao salvar: ${error.message}`, "danger");
  }
};

const resetImportModal = () => {
  document.getElementById("stepPaste")?.classList.remove("d-none");
  document.getElementById("stepReview")?.classList.add("d-none");
  document.getElementById("importLoading")?.classList.add("d-none");
  const textInput = document.getElementById("importText");
  if (textInput) textInput.value = "";
  importedItems = [];
  appState.importer.pendingCategoryIndex = null;
};

const logsState = {
  items: [],
};

const updateLogsPendingBadge = async () => {
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

const renderSystemLogs = () => {
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

const loadSystemLogs = async () => {
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

const initSystemLogs = () => {
  const tableBody = document.getElementById("systemLogsTableBody");
  if (!tableBody) return;
  tableBody.addEventListener("click", handleSystemLogsTableClick);
  loadSystemLogs();
};

// 1. Função para marcar como pago
const markRecurringAsPaid = async (id) => {
    if (!confirm("Confirmar pagamento desta conta?")) return;

    setLoadingState(true);
    try {
        // Envia o ano e mês atuais do appState para saber qual mês estamos pagando
        const payload = {
            year: appState.year,
            month: appState.month
        };

        await apiFetch(`/api/recurring/${id}/pay/`, {
            method: "POST",
            body: JSON.stringify(payload),
        });

        showToast("Conta marcada como paga!", "success");
        loadMonthData(); // Recarrega a tabela para atualizar a cor/status
    } catch (error) {
        showToast(`Erro: ${error.message}`, "danger");
    } finally {
        setLoadingState(false);
    }
};

// 2. Função para editar recorrência via modal
const openRecurringEditModal = (recurringItem) => {
    const modalElement = document.getElementById("recurringModal");
    const form = document.getElementById("recurringForm");
    if (!modalElement || !form) return;

    form.dataset.recurringId = recurringItem.id;
    const title = document.getElementById("recurringModalLabel");
    if (title) title.textContent = "Editar recorrência";

    const submitButton = modalElement.querySelector('button[type="submit"][form="recurringForm"]');
    if (submitButton) submitButton.textContent = "Salvar alterações";

    const categorySelect = document.getElementById("recurringCategory");
    const categoryInput = document.getElementById("recurringNewCategory");
    const toggleButton = document.getElementById("btnToggleNewCatRecurring");

    elements.recurringDescription.value = recurringItem.descricao || "";
    elements.recurringValue.value = recurringItem.valor ?? "";
    elements.recurringDay.value = recurringItem.dia_vencimento ?? "";
    elements.recurringStart.value = recurringItem.inicio || "";
    elements.recurringEnd.value = recurringItem.fim || "";
    elements.recurringActive.checked = Boolean(recurringItem.ativo);

    if (categoryInput) {
        categoryInput.value = "";
        categoryInput.style.display = "none";
    }
    if (categorySelect) {
        categorySelect.style.display = "block";
        categorySelect.value = recurringItem.categoria_id ? String(recurringItem.categoria_id) : "";
    }
    if (toggleButton) toggleButton.textContent = "+";

    bootstrap.Modal.getOrCreateInstance(modalElement).show();
};

const loadMonthData = async () => {
  setLoadingState(true);
  try {
    const data = await apiFetch(
      `/api/month-data/?year=${appState.year}&month=${appState.month}`
    );
    appState.data = data;
    renderAll();
  } catch (error) {
    showToast(`Erro ao carregar dados: ${error.message}`, "danger");
  } finally {
    setLoadingState(false);
  }
};

const renderSummary = () => {
  const { totals } = appState.data;
  elements.totalMonth.textContent = formatCurrency(totals.total_month || 0);
  elements.totalCard.textContent = formatCurrency(totals.total_card || 0);
  elements.totalRecurring.textContent = formatCurrency(totals.total_recurring || 0);
};

const renderCharts = () => {
  const lineCanvas = document.getElementById("lineChart");
  const doughnutCanvas = document.getElementById("doughnutChart");
  if (!lineCanvas && !doughnutCanvas) return;
  if (typeof Chart === "undefined") return;

  const purchases = appState.data.purchases || [];

  if (doughnutCanvas) {
    const totalsByCard = new Map();
    purchases.forEach((item) => {
      const key = item.cartao_nome || "Sem cartão";
      const current = totalsByCard.get(key) || 0;
      totalsByCard.set(key, current + Number(item.valor_parcela || 0));
    });
    const cardLabels = appState.data.cards.length
      ? appState.data.cards.map((card) => card.nome)
      : Array.from(totalsByCard.keys());
    const dataValues = cardLabels.map((label) => totalsByCard.get(label) || 0);
    const colors = [
      "#4c7dff",
      "#22c55e",
      "#f97316",
      "#06b6d4",
      "#a855f7",
      "#f43f5e",
      "#64748b",
    ];
    chartState.doughnut?.destroy();
    chartState.doughnut = new Chart(doughnutCanvas, {
      type: "doughnut",
      data: {
        labels: cardLabels,
        datasets: [
          {
            data: dataValues,
            backgroundColor: cardLabels.map((_, index) => colors[index % colors.length]),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: "bottom",
          },
        },
      },
    });
  }

  if (lineCanvas) {
    const daysInMonth = new Date(appState.year, appState.month, 0).getDate();
    const dailyTotals = Array(daysInMonth).fill(0);
    purchases.forEach((item) => {
      const dueDate = new Date(item.vencimento);
      const dayIndex = dueDate.getDate() - 1;
      if (dayIndex >= 0 && dayIndex < dailyTotals.length) {
        dailyTotals[dayIndex] += Number(item.valor_parcela || 0);
      }
    });
    const cumulativeTotals = [];
    dailyTotals.reduce((acc, value) => {
      const nextValue = acc + value;
      cumulativeTotals.push(nextValue);
      return nextValue;
    }, 0);

    chartState.line?.destroy();
    chartState.line = new Chart(lineCanvas, {
      type: "line",
      data: {
        labels: Array.from({ length: daysInMonth }, (_, index) => `${index + 1}`),
        datasets: [
          {
            label: "Gasto acumulado",
            data: cumulativeTotals,
            borderColor: "#4c7dff",
            backgroundColor: "rgba(76, 125, 255, 0.2)",
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            display: false,
          },
        },
        scales: {
          x: {
            grid: {
              display: false,
            },
          },
        },
      },
    });
  }
};

const renderCards = () => {
  const list = elements.cardList;
  list.innerHTML = "";
  if (!appState.data.cards.length) {
    list.innerHTML = `<p class="text-muted small mb-0">Cadastre cartões para visualizar as faturas.</p>`;
    return;
  }
  appState.data.cards.forEach((card) => {
    const wrapper = document.createElement("div");
    wrapper.className = "card-dropzone";
    wrapper.dataset.cardId = card.id;
    wrapper.innerHTML = `
      <div class="meta">
        <strong>${card.nome}</strong>
        <small class="text-muted">Arraste compras aqui</small>
      </div>
      <div class="value blur-sensitive">${formatCurrency(card.total_mes)}</div>
    `;
    wrapper.addEventListener("dragover", (event) => {
      event.preventDefault();
      wrapper.classList.add("drag-over");
    });
    wrapper.addEventListener("dragleave", () => wrapper.classList.remove("drag-over"));
    wrapper.addEventListener("drop", async (event) => {
      event.preventDefault();
      wrapper.classList.remove("drag-over");
      const purchaseId = event.dataTransfer.getData("text/plain");
      if (!purchaseId) return;
      await updatePurchaseCard(purchaseId, card.id, card.nome);
    });
    list.appendChild(wrapper);
  });
};

const applyPurchaseFilters = (purchases) => {
  const search = appState.filters.purchaseSearch.toLowerCase();
  return purchases
    .filter((item) =>
      item.descricao.toLowerCase().includes(search)
    )
    .filter((item) =>
      appState.filters.purchaseCard === "all"
        ? true
        : item.cartao_id === Number(appState.filters.purchaseCard)
    )
    .filter((item) => {
      if (appState.filters.purchaseType === "all") return true;
      const isInstallment = item.parcelas > 1;
      return appState.filters.purchaseType === "installment" ? isInstallment : !isInstallment;
    })
    .sort((a, b) => {
      if (appState.filters.purchaseSort === "value") {
        return Number(b.valor_parcela) - Number(a.valor_parcela);
      }
      return new Date(a.vencimento) - new Date(b.vencimento);
    });
};

const applyRecurringFilters = (items) => {
  const search = appState.filters.recurringSearch.toLowerCase();
  return items
    .filter((item) => item.descricao.toLowerCase().includes(search))
    .sort((a, b) => {
      if (appState.filters.recurringSort === "value") {
        return Number(b.valor) - Number(a.valor);
      }
      return new Date(a.vencimento) - new Date(b.vencimento);
    });
};

const createEditableCell = (value, inputType, inputValue, inputClass = "form-control form-control-sm") => {
  const wrapper = document.createElement("div");
  wrapper.className = "editable-field";
  const view = document.createElement("span");
  view.className = "view-value";
  view.textContent = value;
  const input = document.createElement("input");
  input.type = inputType;
  input.value = inputValue;
  input.className = `edit-input ${inputClass}`;
  wrapper.appendChild(view);
  wrapper.appendChild(input);
  return { wrapper, input, view };
};

const cardBadgeVariants = ["primary", "success", "info", "warning", "danger", "secondary", "dark"];

const getCardBadgeVariant = (name) => {
  if (!name) return cardBadgeVariants[0];
  let hash = 0;
  Array.from(name).forEach((char) => {
    hash = (hash + char.charCodeAt(0)) % cardBadgeVariants.length;
  });
  return cardBadgeVariants[hash];
};

const renderPurchaseTable = () => {
  const data = applyPurchaseFilters(appState.data.purchases || []);
  elements.purchaseTableBody.innerHTML = "";
  elements.purchaseEmpty.style.display = data.length ? "none" : "block";

  data.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.purchaseId = item.id;
    row.draggable = true;
    row.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", item.id);
      event.dataTransfer.effectAllowed = "move";
    });

    const descriptionCell = document.createElement("td");
    const descriptionEditable = createEditableCell(item.descricao, "text", item.descricao);
    descriptionCell.appendChild(descriptionEditable.wrapper);

    const cardCell = document.createElement("td");
    const cardVariant = getCardBadgeVariant(item.cartao_nome);
    cardCell.innerHTML = `<span class="badge text-bg-${cardVariant}">${item.cartao_nome}</span>`;

    const categoryCell = document.createElement("td");
    const categoryName = appState.categories?.find((cat) => cat.id === item.categoria_id)?.nome;
    categoryCell.innerHTML = categoryName
      ? `<span class="badge bg-secondary">${categoryName}</span>`
      : '<span class="text-muted">-</span>';

    const installmentCell = document.createElement("td");
    if (item.parcelas === 1) {
      installmentCell.innerHTML = `
        <span class="badge text-bg-success d-inline-flex align-items-center gap-1">
          <i class="bi bi-check-circle-fill"></i>
          À vista
        </span>
      `;
    } else {
      const progressValue = Math.round((item.parcela_atual / item.parcelas) * 100);
      installmentCell.innerHTML = `
        <div class="d-flex flex-column gap-1">
          <span class="badge text-bg-warning text-dark align-self-start">${item.parcela_atual}/${item.parcelas}</span>
          <div class="progress" style="height: 6px;">
            <div class="progress-bar bg-warning" role="progressbar" style="width: ${progressValue}%"></div>
          </div>
        </div>
      `;
    }

    const dueCell = document.createElement("td");
    const dueEditable = createEditableCell(formatDate(item.primeiro_vencimento), "date", item.primeiro_vencimento);
    dueCell.appendChild(dueEditable.wrapper);

    const valueCell = document.createElement("td");
    valueCell.className = "text-end";
    const valueEditable = createEditableCell(formatCurrency(item.valor_parcela), "number", item.valor_total, "form-control form-control-sm text-end");
    valueEditable.wrapper.classList.add("blur-sensitive");
    valueCell.appendChild(valueEditable.wrapper);

    const actionsCell = document.createElement("td");
    actionsCell.className = "text-end";
    actionsCell.innerHTML = `
      <div class="row-actions">
        <button class="btn btn-outline-secondary btn-sm" data-action="edit">Editar</button>
        <button class="btn btn-outline-danger btn-sm" data-action="delete">Excluir</button>
      </div>
    `;

    row.append(
      descriptionCell,
      cardCell,
      categoryCell,
      installmentCell,
      dueCell,
      valueCell,
      actionsCell
    );
    elements.purchaseTableBody.appendChild(row);

    const setEditing = (isEditing) => {
      [descriptionEditable.wrapper, dueEditable.wrapper, valueEditable.wrapper].forEach((field) => {
        field.classList.toggle("is-editing", isEditing);
      });
      actionsCell.innerHTML = isEditing
        ? `
          <div class="row-actions">
            <button class="btn btn-primary btn-sm" data-action="save">Salvar</button>
            <button class="btn btn-light btn-sm" data-action="cancel">Cancelar</button>
          </div>
        `
        : `
          <div class="row-actions">
            <button class="btn btn-outline-secondary btn-sm" data-action="edit">Editar</button>
            <button class="btn btn-outline-danger btn-sm" data-action="delete">Excluir</button>
          </div>
        `;
    };

    actionsCell.addEventListener("click", async (event) => {
      const action = event.target.dataset.action;
      if (!action) return;
      if (action === "edit") {
        setEditing(true);
      }
      if (action === "cancel") {
        descriptionEditable.input.value = item.descricao;
        dueEditable.input.value = item.primeiro_vencimento;
        valueEditable.input.value = item.valor_total;
        setEditing(false);
      }
      if (action === "save") {
        const updated = {
          descricao: descriptionEditable.input.value.trim(),
          primeiro_vencimento: dueEditable.input.value,
          valor_total: Number(valueEditable.input.value || 0),
          parcelas: item.parcelas,
        };
        if (!updated.descricao || !updated.primeiro_vencimento) {
          showToast("Preencha todos os campos obrigatórios.", "danger");
          return;
        }
        setEditing(false);
        const previous = { ...item };
        Object.assign(item, updated);
        renderPurchaseTable();
        try {
          await apiFetch(`/api/card-purchase/${item.id}/`, {
            method: "PATCH",
            body: JSON.stringify(updated),
          });
          showToast("Compra atualizada com sucesso.");
          await loadMonthData();
        } catch (error) {
          Object.assign(item, previous);
          renderPurchaseTable();
          showToast(`Erro ao atualizar compra: ${error.message}`, "danger");
        }
      }
      if (action === "delete") {
        openConfirmDelete(`Excluir compra "${item.descricao}"?`, async () => {
          const previousData = [...appState.data.purchases];
          appState.data.purchases = appState.data.purchases.filter((purchase) => purchase.id !== item.id);
          renderPurchaseTable();
          try {
            await apiFetch(`/api/card-purchase/${item.id}/`, { method: "DELETE" });
            showToast("Compra excluída.");
            await loadMonthData();
          } catch (error) {
            appState.data.purchases = previousData;
            renderPurchaseTable();
            showToast(`Erro ao excluir compra: ${error.message}`, "danger");
          }
        });
      }
    });
  });
};

// --- BLOCO 3: Mostrar Categoria na Tabela ---
// --- BLOCO 3: Mostrar Categoria na Tabela (CORRIGIDO) ---
const renderRecurringTable = () => {
  const tbody = document.querySelector("#recurringTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  let filtered = appState.data.recurring.filter((r) =>
    r.descricao.toLowerCase().includes(appState.filters.recurringSearch.toLowerCase())
  );

  // Ordenação
  filtered.sort((a, b) => {
    if (appState.filters.recurringSort === "date") return a.dia_vencimento - b.dia_vencimento;
    if (appState.filters.recurringSort === "value") return b.valor - a.valor;
    return 0;
  });

  filtered.forEach((r) => {
    // AQUI: A variável chama-se 'tr'
    const tr = document.createElement("tr");
    tr.dataset.id = r.id;
    if (!r.ativo) tr.classList.add("text-muted", "bg-light");

    // 1. Dia
    const dayCell = document.createElement("td");
    dayCell.textContent = r.dia_vencimento;
    tr.appendChild(dayCell);

    // 2. Descrição
    const descCell = document.createElement("td");
    descCell.innerHTML = `<div class="fw-medium">${r.descricao}</div><small class="text-muted">Desde ${new Date(r.inicio).toLocaleDateString("pt-BR")}</small>`;
    tr.appendChild(descCell);

    // 3. Categoria
    const categoryCell = document.createElement("td");
    categoryCell.innerHTML = r.categoria_nome
      ? `<span class="badge bg-secondary">${r.categoria_nome}</span>`
      : '<span class="text-muted">Sem categoria</span>';
    tr.appendChild(categoryCell);

    // 4. Valor
    const valCell = document.createElement("td");
    valCell.innerHTML = `<span class="blur-sensitive">${currencyFormatter.format(r.valor)}</span>`;
    tr.appendChild(valCell);

    // 5. Status
    const statusCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    statusBadge.className = `badge ${r.ativo ? (r.is_paid ? "bg-success" : "bg-warning text-dark") : "bg-secondary"}`;
    statusBadge.textContent = r.ativo ? (r.is_paid ? "Pago" : "Pendente") : "Inativo";
    statusCell.appendChild(statusBadge);
    tr.appendChild(statusCell);

    // 6. Ações (CORRIGIDO)
    const actCell = document.createElement("td");
    actCell.className = "text-end";

    if (r.ativo) {
      // Botão Editar
      const editBtn = document.createElement("button");
      editBtn.className = "btn btn-sm btn-outline-secondary me-2";
      editBtn.innerHTML = '<i class="bi bi-pencil"></i>';
      editBtn.title = "Editar recorrência";
      editBtn.onclick = () => openRecurringEditModal(r);
      actCell.appendChild(editBtn);

      // Lógica de Pagamento
      if (!r.is_paid) {
        // Botão Pagar
        const payBtn = document.createElement("button");
        payBtn.className = "btn btn-sm btn-outline-success me-2";
        payBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
        payBtn.title = "Marcar como Pago";
        payBtn.onclick = () => markRecurringAsPaid(r.id);
        actCell.appendChild(payBtn);
      } else {
        // Badge Pago (Visual apenas)
        const paidBadge = document.createElement("span");
        paidBadge.className = "badge bg-success me-2";
        paidBadge.innerText = "Pago";
        actCell.appendChild(paidBadge);
      }
    }

    // Botão Excluir (Sempre visível)
    const delBtn = document.createElement("button");
    delBtn.className = "btn btn-sm btn-link text-danger p-0";
    delBtn.innerHTML = '<i class="bi bi-trash"></i>';
    // Nota: Certifica-te que tens a função deleteRecurring ou deleteRecurringExpense definida algures.
    // Se não tiveres, comenta a linha abaixo para evitar erro.
    if (typeof deleteRecurring === 'function') {
        delBtn.onclick = () => deleteRecurring(r.id);
    } else {
        // Fallback caso a função tenha outro nome ou não exista
        delBtn.onclick = () => console.log("Função deleteRecurring não encontrada");
    }

    actCell.appendChild(delBtn);

    // AQUI ESTAVA O ERRO: Usamos 'tr' e não 'row'
    tr.appendChild(actCell);

    tbody.appendChild(tr);
  });
};
const renderPurchaseFilters = () => {
  const cardFilter = elements.purchaseCardFilter;
  cardFilter.innerHTML = `<option value="all">Todos</option>`;
  appState.data.cards.forEach((card) => {
    cardFilter.insertAdjacentHTML("beforeend", `<option value="${card.id}">${card.nome}</option>`);
  });
  cardFilter.value = appState.filters.purchaseCard;
};

const renderCardOptions = () => {
  if (!elements.purchaseCard) return;
  elements.purchaseCard.innerHTML = "";
  if (!appState.data.cards.length) {
    elements.purchaseCard.insertAdjacentHTML(
      "beforeend",
      `<option value="">Cadastre um cartão primeiro</option>`
    );
    return;
  }
  appState.data.cards.forEach((card) => {
    elements.purchaseCard.insertAdjacentHTML(
      "beforeend",
      `<option value="${card.id}">${card.nome}</option>`
    );
  });
};

const renderAll = () => {
  renderSummary();
  renderCharts();
  renderCards();
  renderCardOptions();
  renderPurchaseFilters();
  renderPurchaseTable();
  renderRecurringTable();
};

const updatePurchaseCard = async (purchaseId, newCardId, newCardName) => {
  const purchase = appState.data.purchases.find((item) => String(item.id) === String(purchaseId));
  if (!purchase || purchase.cartao_id === newCardId) return;
  const previous = { ...purchase };
  purchase.cartao_id = newCardId;
  purchase.cartao_nome = newCardName;
  renderPurchaseTable();
  try {
    await apiFetch(`/api/card-purchase/${purchaseId}/`, {
      method: "PATCH",
      body: JSON.stringify({ cartao_id: newCardId }),
    });
    showToast("Cartão atualizado.");
    await loadMonthData();
  } catch (error) {
    Object.assign(purchase, previous);
    renderPurchaseTable();
    showToast(`Erro ao mover compra: ${error.message}`, "danger");
  }
};

const openConfirmDelete = (message, onConfirm) => {
  const modalElement = document.getElementById("confirmDeleteModal");
  const messageElement = document.getElementById("confirmDeleteMessage");
  const confirmButton = document.getElementById("confirmDeleteButton");
  if (!modalElement || !confirmButton || !messageElement) return;

  messageElement.textContent = message;
  const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
  const handler = async () => {
    confirmButton.removeEventListener("click", handler);
    confirmButton.disabled = true;
    const originalText = confirmButton.textContent;
    confirmButton.textContent = confirmButton.dataset.loadingText || "Excluindo...";
    await onConfirm();
    confirmButton.disabled = false;
    confirmButton.textContent = originalText;
    modal.hide();
  };
  confirmButton.addEventListener("click", handler);
  modal.show();
};

const handlePurchaseSubmit = async (event) => {
  event.preventDefault();
  const form = event.target;

  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }

  // 1. Ler os novos campos do DOM
  const tipoPagamentoInput = document.querySelector('input[name="tipo_pagamento"]:checked');
  const tipoPagamento = tipoPagamentoInput ? tipoPagamentoInput.value : 'CREDITO';
  const newCatName = document.getElementById('purchaseNewCategory').value;
  const catId = document.getElementById('purchaseCategory').value;

  // 2. Montar o objeto Payload com lógica condicional
  const payload = {
    // Só envia cartão se for CREDITO
    cartao_id: tipoPagamento === 'CREDITO' ? Number(elements.purchaseCard.value) : null,
    tipo_pagamento: tipoPagamento,
    descricao: elements.purchaseDescription.value.trim(),
    valor_total: Number(elements.purchaseTotal.value),
    // Se não for crédito, é sempre 1 parcela
    parcelas: tipoPagamento === 'CREDITO' ? Number(elements.purchaseInstallments.value) : 1,
    primeiro_vencimento: elements.purchaseFirstDue.value,
    categoria: catId ? Number(catId) : null,
    nova_categoria: newCatName || null
  };

  // 3. Validação específica
  if (payload.tipo_pagamento === 'CREDITO' && !payload.cartao_id) {
    showToast("Selecione um cartão válido para compras no crédito.", "danger");
    return;
  }

  // 4. Item Temporário para a Tabela (Feedback Instantâneo)
  const tempId = `temp-${Date.now()}`;

  // Definimos o nome visual: se tiver cartão usa o nome dele, senão usa o Tipo (ex: "PIX")
  let displayCardName = "";
  if (payload.cartao_id) {
      displayCardName = elements.purchaseCard.selectedOptions[0]?.textContent || "Cartão";
  } else {
      displayCardName = payload.tipo_pagamento; // Exibe "PIX", "DEBITO", etc.
  }

  const tempItem = {
    id: tempId,
    cartao_id: payload.cartao_id,
    cartao_nome: displayCardName,
    descricao: payload.descricao,
    parcelas: payload.parcelas,
    parcela_atual: 1,
    valor_total: payload.valor_total,
    valor_parcela: payload.valor_total / payload.parcelas,
    primeiro_vencimento: payload.primeiro_vencimento,
    vencimento: payload.primeiro_vencimento,
  };

  appState.data.purchases.unshift(tempItem);
  renderPurchaseTable();

  try {
    await apiFetch("/api/card-purchase/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    showToast("Compra adicionada.");

    // Reset do Formulário e UI
    form.reset();
    form.classList.remove("was-validated");

    // Resetar visual dos campos extras
    const newCatInput = document.getElementById('purchaseNewCategory');
    const catSelect = document.getElementById('purchaseCategory');
    const toggleBtn = document.getElementById('btnToggleNewCat');

    if(newCatInput) newCatInput.style.display = 'none';
    if(catSelect) catSelect.style.display = 'block';
    if(toggleBtn) toggleBtn.textContent = '+';

    // Resetar rádio para Crédito
    const creditRadio = document.getElementById('typeCredit');
    if(creditRadio) {
        creditRadio.checked = true;
        creditRadio.dispatchEvent(new Event('change'));
    }

    bootstrap.Modal.getInstance(document.getElementById("purchaseModal"))?.hide();

    // Recarregar dados reais (importante para pegar a nova categoria criada, se houver)
    await loadMonthData();
    // Se criou categoria nova, recarrega o select de categorias
    if (payload.nova_categoria) {
        loadCategories();
    }

  } catch (error) {
    // Remove o item temporário se der erro
    appState.data.purchases = appState.data.purchases.filter((item) => item.id !== tempId);
    renderPurchaseTable();
    showToast(`Erro ao salvar compra: ${error.message}`, "danger");
  }
};
// --- BLOCO 2: Salvar Recorrência com Categoria ---
const handleRecurringSubmit = async (event) => {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }

  // LER CATEGORIAS (Novidade)
  const recurringId = form.dataset.recurringId;
  const newCatName = document.getElementById('recurringNewCategory').value;
  const catId = document.getElementById('recurringCategory').value;

  const payload = {
    descricao: elements.recurringDescription.value.trim(),
    valor: Number(elements.recurringValue.value),
    dia_vencimento: Number(elements.recurringDay.value),
    inicio: elements.recurringStart.value,
    fim: elements.recurringEnd.value || null,
    ativo: elements.recurringActive.checked,
    // ENVIAR CATEGORIAS (Novidade)
    categoria: catId ? Number(catId) : null,
    nova_categoria: newCatName || null
  };

  try {
    if (recurringId) {
      await apiFetch(`/api/recurring-expense/${recurringId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      showToast("Recorrência atualizada.");
    } else {
      await apiFetch("/api/recurring-expense/", { method: "POST", body: JSON.stringify(payload) });
      showToast("Recorrência adicionada.");
    }
    form.reset();
    form.classList.remove("was-validated");

    // RESETAR VISUAL DA CATEGORIA
    document.getElementById('recurringNewCategory').style.display = 'none';
    document.getElementById('recurringCategory').style.display = 'block';
    const btn = document.getElementById('btnToggleNewCatRecurring');
    if(btn) btn.textContent = '+';

    delete form.dataset.recurringId;
    const title = document.getElementById("recurringModalLabel");
    if (title) title.textContent = "Nova recorrência";
    const submitButton = document.querySelector('button[type="submit"][form="recurringForm"]');
    if (submitButton) submitButton.textContent = "Salvar recorrência";

    bootstrap.Modal.getInstance(document.getElementById("recurringModal"))?.hide();
    await loadMonthData();
    // Se criou categoria nova, recarrega as listas
    if (payload.nova_categoria) loadCategories();
  } catch (error) {
    showToast(`Erro ao salvar recorrência: ${error.message}`, "danger");
  }
};
const bindEvents = () => {
  // --- Eventos de Navegação e Filtros (Originais) ---
  elements.monthSelect.addEventListener("change", () => {
    appState.month = Number(elements.monthSelect.value);
    loadMonthData();
  });
  elements.yearSelect.addEventListener("change", () => {
    appState.year = Number(elements.yearSelect.value);
    loadMonthData();
  });
  elements.refreshButton.addEventListener("click", loadMonthData);

  elements.purchaseSearch.addEventListener("input", (event) => {
    appState.filters.purchaseSearch = event.target.value;
    renderPurchaseTable();
  });
  elements.purchaseCardFilter.addEventListener("change", (event) => {
    appState.filters.purchaseCard = event.target.value;
    renderPurchaseTable();
  });
  elements.purchaseTypeFilter.addEventListener("change", (event) => {
    appState.filters.purchaseType = event.target.value;
    renderPurchaseTable();
  });
  elements.purchaseSort.addEventListener("change", (event) => {
    appState.filters.purchaseSort = event.target.value;
    renderPurchaseTable();
  });

  elements.recurringSearch.addEventListener("input", (event) => {
    appState.filters.recurringSearch = event.target.value;
    renderRecurringTable();
  });
  elements.recurringSort.addEventListener("change", (event) => {
    appState.filters.recurringSort = event.target.value;
    renderRecurringTable();
  });

  document.getElementById("purchaseForm")?.addEventListener("submit", handlePurchaseSubmit);
  document.getElementById("recurringForm")?.addEventListener("submit", handleRecurringSubmit);
  document.getElementById("categoryForm")?.addEventListener("submit", handleCategorySubmit);

  // --- BLOCO 4: Listener do Botão da Categoria (Recorrência) ---
  // Colar isto DENTRO de bindEvents, pode ser no final, antes do } de fecho.

  const btnToggleCatRec = document.getElementById("btnToggleNewCatRecurring");
  if (btnToggleCatRec) {
    btnToggleCatRec.addEventListener("click", () => {
      const select = document.getElementById("recurringCategory");
      const input = document.getElementById("recurringNewCategory");
      if (input.style.display === "none") {
        input.style.display = "block"; select.style.display = "none"; input.focus(); btnToggleCatRec.textContent = "x";
      } else {
        input.style.display = "none"; select.style.display = "block"; input.value = ""; btnToggleCatRec.textContent = "+";
      }
    });
  }

  // Adicionar também este reset no evento do modal recurringModal
  document.getElementById("recurringModal")?.addEventListener("shown.bs.modal", () => {
    // Reset visual
    const inputCat = document.getElementById("recurringNewCategory");
    const selectCat = document.getElementById("recurringCategory");
    const btnCat = document.getElementById("btnToggleNewCatRecurring");
    if (inputCat) { inputCat.style.display = "none"; inputCat.value = ""; }
    if (selectCat) selectCat.style.display = "block";
    if (btnCat) btnCat.textContent = "+";

    // Foca na descrição (código que já deves ter)
    elements.recurringDescription.focus();
  });

  document.getElementById("recurringModal")?.addEventListener("hidden.bs.modal", () => {
    const form = document.getElementById("recurringForm");
    if (!form) return;
    delete form.dataset.recurringId;
    const title = document.getElementById("recurringModalLabel");
    if (title) title.textContent = "Nova recorrência";
    const submitButton = document.querySelector('button[type="submit"][form="recurringForm"]');
    if (submitButton) submitButton.textContent = "Salvar recorrência";
  });

  // --- NOVA LÓGICA: Alternar campos por Tipo de Pagamento ---
  const paymentRadios = document.querySelectorAll('input[name="tipo_pagamento"]');
  paymentRadios.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      const type = e.target.value;
      // Seleciona elementos com segurança
      const cardFields = document.getElementById("creditCardFields");
      const instGroup = document.getElementById("installmentsGroup");
      const instInput = document.getElementById("purchaseInstallments");
      const cardInput = document.getElementById("purchaseCard");

      if (type === "CREDITO") {
        if (cardFields) cardFields.style.display = "block";
        if (instGroup) instGroup.style.visibility = "visible";
        if (cardInput) cardInput.setAttribute("required", "required");
      } else {
        if (cardFields) cardFields.style.display = "none";
        if (instGroup) instGroup.style.visibility = "hidden";
        if (instInput) instInput.value = 1;
        if (cardInput) {
          cardInput.removeAttribute("required");
          cardInput.value = "";
        }
      }
    });
  });

  // --- NOVA LÓGICA: Alternar Nova Categoria (+ / x) ---
  const btnToggleCat = document.getElementById("btnToggleNewCat");
  if (btnToggleCat) {
    btnToggleCat.addEventListener("click", () => {
      const select = document.getElementById("purchaseCategory");
      const input = document.getElementById("purchaseNewCategory");

      if (input.style.display === "none") {
        // Modo: Digitar nova categoria
        input.style.display = "block";
        select.style.display = "none";
        input.focus();
        btnToggleCat.textContent = "x";
      } else {
        // Modo: Selecionar existente
        input.style.display = "none";
        select.style.display = "block";
        input.value = "";
        btnToggleCat.textContent = "+";
      }
    });
  }

  // --- Comportamento ao Abrir Modais ---
  document.getElementById("purchaseModal")?.addEventListener("show.bs.modal", (event) => {
    // 1. Resetar visual para "Crédito" sempre que abrir
    const creditRadio = document.getElementById("typeCredit");
    if (creditRadio) {
      creditRadio.checked = true;
      creditRadio.dispatchEvent(new Event("change")); // Força atualização dos campos
    }

    // 2. Resetar visual da Categoria (voltar para select)
    const inputCat = document.getElementById("purchaseNewCategory");
    const selectCat = document.getElementById("purchaseCategory");
    const btnCat = document.getElementById("btnToggleNewCat");
    if (inputCat) { inputCat.style.display = "none"; inputCat.value = ""; }
    if (selectCat) selectCat.style.display = "block";
    if (btnCat) btnCat.textContent = "+";

    // 3. Lógica original de parcelas (Single vs Installments)
    const trigger = event.relatedTarget;
    const mode = trigger?.dataset.mode;
    const installmentsInput = elements.purchaseInstallments;

    if (mode === "single") {
      installmentsInput.value = 1;
      installmentsInput.setAttribute("readonly", "readonly");
    } else {
      installmentsInput.removeAttribute("readonly");
      installmentsInput.value = Math.max(Number(installmentsInput.value) || 2, 2);
    }

    // Tenta focar na descrição
    if (elements.purchaseDescription) {
        elements.purchaseDescription.focus();
    }
  });

  document.getElementById("recurringModal")?.addEventListener("shown.bs.modal", () => {
    elements.recurringDescription.focus();
  });
};

const init = () => {
  updateLogsPendingBadge();
  initSystemLogs();
  initPrivacyToggle();

  if (!document.getElementById("monthSelect")) {
    return;
  }

  elements.monthSelect = document.getElementById("monthSelect");
  elements.yearSelect = document.getElementById("yearSelect");
  elements.refreshButton = document.getElementById("refreshButton");
  elements.totalMonth = document.getElementById("totalMonth");
  elements.totalCard = document.getElementById("totalCard");
  elements.totalRecurring = document.getElementById("totalRecurring");
  elements.cardList = document.getElementById("cardList");
  elements.purchaseTableBody = document.getElementById("purchaseTableBody");
  elements.recurringTableBody = document.getElementById("recurringTableBody");
  elements.purchaseEmpty = document.getElementById("purchaseEmpty");
  elements.recurringEmpty = document.getElementById("recurringEmpty");
  elements.purchaseSearch = document.getElementById("purchaseSearch");
  elements.purchaseCardFilter = document.getElementById("purchaseCardFilter");
  elements.purchaseTypeFilter = document.getElementById("purchaseTypeFilter");
  elements.purchaseSort = document.getElementById("purchaseSort");
  elements.recurringSearch = document.getElementById("recurringSearch");
  elements.recurringSort = document.getElementById("recurringSort");
  elements.purchaseCard = document.getElementById("purchaseCard");
  elements.purchaseDescription = document.getElementById("purchaseDescription");
  elements.purchaseTotal = document.getElementById("purchaseTotal");
  elements.purchaseInstallments = document.getElementById("purchaseInstallments");
  elements.purchaseFirstDue = document.getElementById("purchaseFirstDue");
  elements.recurringDescription = document.getElementById("recurringDescription");
  elements.recurringValue = document.getElementById("recurringValue");
  elements.recurringDay = document.getElementById("recurringDay");
  elements.recurringStart = document.getElementById("recurringStart");
  elements.recurringEnd = document.getElementById("recurringEnd");
  elements.recurringActive = document.getElementById("recurringActive");

  const body = document.body;
  appState.month = Number(body.dataset.month);
  appState.year = Number(body.dataset.year);

  populateMonthSelectors();
  updateSelectors();
  loadCategories();
  bindEvents();
  loadMonthData();
  initImporter(loadMonthData);
};

document.addEventListener("DOMContentLoaded", init);
