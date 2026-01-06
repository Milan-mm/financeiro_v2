const appState = {
  year: null,
  month: null,
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

const elements = {};
const chartState = {
  line: null,
  doughnut: null,
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
    let errorDetail = "";
    try {
      const data = await response.json();
      errorDetail = data.error || JSON.stringify(data);
    } catch (error) {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail || "Erro inesperado.");
  }
  return response.json();
};

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

const setLoadingState = (isLoading) => {
  if (!isLoading) return;
  elements.purchaseTableBody.innerHTML = `<tr class="skeleton-row"><td colspan="6"><div class="skeleton-line"></div></td></tr>`;
  elements.recurringTableBody.innerHTML = `<tr class="skeleton-row"><td colspan="5"><div class="skeleton-line"></div></td></tr>`;
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
      <div class="value">${formatCurrency(card.total_mes)}</div>
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
    valueCell.appendChild(valueEditable.wrapper);

    const actionsCell = document.createElement("td");
    actionsCell.className = "text-end";
    actionsCell.innerHTML = `
      <div class="row-actions">
        <button class="btn btn-outline-secondary btn-sm" data-action="edit">Editar</button>
        <button class="btn btn-outline-danger btn-sm" data-action="delete">Excluir</button>
      </div>
    `;

    row.append(descriptionCell, cardCell, installmentCell, dueCell, valueCell, actionsCell);
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

const renderRecurringTable = () => {
  const data = applyRecurringFilters(appState.data.recurring || []);
  elements.recurringTableBody.innerHTML = "";
  elements.recurringEmpty.style.display = data.length ? "none" : "block";

  data.forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.recurringId = item.id;

    const paidCell = document.createElement("td");
    const paidWrapper = document.createElement("div");
    paidWrapper.className = "form-check m-0 d-flex justify-content-center";
    const paidCheckbox = document.createElement("input");
    paidCheckbox.type = "checkbox";
    paidCheckbox.className = "form-check-input";
    paidCheckbox.checked = Boolean(item.is_paid);
    paidWrapper.appendChild(paidCheckbox);
    paidCell.appendChild(paidWrapper);

    const descriptionCell = document.createElement("td");
    const descriptionEditable = createEditableCell(item.descricao, "text", item.descricao);
    descriptionCell.appendChild(descriptionEditable.wrapper);

    const dueCell = document.createElement("td");
    const dueEditable = createEditableCell(`Dia ${item.dia_vencimento}`, "number", item.dia_vencimento);
    dueCell.appendChild(dueEditable.wrapper);

    const valueCell = document.createElement("td");
    valueCell.className = "text-end";
    const valueEditable = createEditableCell(formatCurrency(item.valor), "number", item.valor, "form-control form-control-sm text-end");
    valueCell.appendChild(valueEditable.wrapper);

    const actionsCell = document.createElement("td");
    actionsCell.className = "text-end";
    actionsCell.innerHTML = `
      <div class="row-actions">
        <button class="btn btn-outline-secondary btn-sm" data-action="edit">Editar</button>
        <button class="btn btn-outline-danger btn-sm" data-action="delete">Excluir</button>
      </div>
    `;

    const setPaidState = (isPaid) => {
      row.classList.toggle("text-decoration-line-through", isPaid);
      row.classList.toggle("text-muted", isPaid);
    };

    setPaidState(Boolean(item.is_paid));

    paidCheckbox.addEventListener("change", async () => {
      const previousValue = item.is_paid;
      const nextValue = paidCheckbox.checked;
      item.is_paid = nextValue;
      setPaidState(nextValue);
      try {
        const response = await apiFetch("/api/recurring-payment-toggle/", {
          method: "POST",
          body: JSON.stringify({
            expense_id: item.id,
            year: appState.year,
            month: appState.month,
          }),
        });
        item.is_paid = Boolean(response.is_paid);
        paidCheckbox.checked = item.is_paid;
        setPaidState(item.is_paid);
      } catch (error) {
        item.is_paid = previousValue;
        paidCheckbox.checked = previousValue;
        setPaidState(previousValue);
        showToast("Não foi possível atualizar o pagamento.", "danger");
      }
    });

    row.append(paidCell, descriptionCell, dueCell, valueCell, actionsCell);
    elements.recurringTableBody.appendChild(row);

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
        dueEditable.input.value = item.dia_vencimento;
        valueEditable.input.value = item.valor;
        setEditing(false);
      }
      if (action === "save") {
        const updated = {
          descricao: descriptionEditable.input.value.trim(),
          dia_vencimento: Number(dueEditable.input.value),
          valor: Number(valueEditable.input.value || 0),
        };
        if (!updated.descricao || !updated.dia_vencimento) {
          showToast("Preencha todos os campos obrigatórios.", "danger");
          return;
        }
        setEditing(false);
        const previous = { ...item };
        Object.assign(item, updated);
        renderRecurringTable();
        try {
          await apiFetch(`/api/recurring-expense/${item.id}/`, {
            method: "PATCH",
            body: JSON.stringify(updated),
          });
          showToast("Recorrência atualizada.");
          await loadMonthData();
        } catch (error) {
          Object.assign(item, previous);
          renderRecurringTable();
          showToast(`Erro ao atualizar recorrência: ${error.message}`, "danger");
        }
      }
      if (action === "delete") {
        openConfirmDelete(`Excluir recorrência "${item.descricao}"?`, async () => {
          const previousData = [...appState.data.recurring];
          appState.data.recurring = appState.data.recurring.filter((rec) => rec.id !== item.id);
          renderRecurringTable();
          try {
            await apiFetch(`/api/recurring-expense/${item.id}/`, { method: "DELETE" });
            showToast("Recorrência excluída.");
            await loadMonthData();
          } catch (error) {
            appState.data.recurring = previousData;
            renderRecurringTable();
            showToast(`Erro ao excluir recorrência: ${error.message}`, "danger");
          }
        });
      }
    });
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
  const payload = {
    cartao_id: Number(elements.purchaseCard.value),
    descricao: elements.purchaseDescription.value.trim(),
    valor_total: Number(elements.purchaseTotal.value),
    parcelas: Number(elements.purchaseInstallments.value),
    primeiro_vencimento: elements.purchaseFirstDue.value,
  };
  if (!payload.cartao_id) {
    showToast("Selecione um cartão válido.", "danger");
    return;
  }
  const tempId = `temp-${Date.now()}`;
  const tempItem = {
    id: tempId,
    cartao_id: payload.cartao_id,
    cartao_nome: elements.purchaseCard.selectedOptions[0]?.textContent || "",
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
    form.reset();
    form.classList.remove("was-validated");
    bootstrap.Modal.getInstance(document.getElementById("purchaseModal"))?.hide();
    await loadMonthData();
  } catch (error) {
    appState.data.purchases = appState.data.purchases.filter((item) => item.id !== tempId);
    renderPurchaseTable();
    showToast(`Erro ao salvar compra: ${error.message}`, "danger");
  }
};

const handleRecurringSubmit = async (event) => {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }
  const payload = {
    descricao: elements.recurringDescription.value.trim(),
    valor: Number(elements.recurringValue.value),
    dia_vencimento: Number(elements.recurringDay.value),
    inicio: elements.recurringStart.value,
    fim: elements.recurringEnd.value || null,
    ativo: elements.recurringActive.checked,
  };
  const tempId = `temp-${Date.now()}`;
  const tempItem = {
    id: tempId,
    descricao: payload.descricao,
    valor: payload.valor,
    dia_vencimento: payload.dia_vencimento,
    vencimento: payload.inicio,
  };
  appState.data.recurring.unshift(tempItem);
  renderRecurringTable();
  try {
    await apiFetch("/api/recurring-expense/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast("Recorrência adicionada.");
    form.reset();
    form.classList.remove("was-validated");
    bootstrap.Modal.getInstance(document.getElementById("recurringModal"))?.hide();
    await loadMonthData();
  } catch (error) {
    appState.data.recurring = appState.data.recurring.filter((item) => item.id !== tempId);
    renderRecurringTable();
    showToast(`Erro ao salvar recorrência: ${error.message}`, "danger");
  }
};

const bindEvents = () => {
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

  document.getElementById("purchaseModal")?.addEventListener("show.bs.modal", (event) => {
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
    elements.purchaseDescription.focus();
  });

  document.getElementById("recurringModal")?.addEventListener("shown.bs.modal", () => {
    elements.recurringDescription.focus();
  });
};

const init = () => {
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
  bindEvents();
  loadMonthData();
};

document.addEventListener("DOMContentLoaded", init);
