import { appState, elements } from "./modules/state.js";
import { apiFetch } from "./modules/api.js";
import { showToast } from "./modules/utils.js";
import { setLoadingState, populateMonthSelectors, updateSelectors } from "./modules/ui.js";
import { renderCharts } from "./modules/charts.js";
import {
  renderSummary,
  renderCards,
  renderPurchaseTable,
  renderRecurringTable,
} from "./modules/tables.js";
import { initSystemLogs, updateLogsPendingBadge } from "./modules/logger.js";
import { initImporter } from './modules/importer.js';

export const loadCategories = async () => {
  try {
    const cats = await apiFetch("/api/categories/");

    const selectPurchase = document.getElementById("purchaseCategory");
    if (selectPurchase) {
      selectPurchase.innerHTML = '<option value="">Sem categoria</option>';
      cats.forEach((c) =>
        selectPurchase.insertAdjacentHTML("beforeend", `<option value="${c.id}">${c.nome}</option>`)
      );
    }

    const selectRecurring = document.getElementById("recurringCategory");
    if (selectRecurring) {
      selectRecurring.innerHTML = '<option value="">Sem categoria</option>';
      cats.forEach((c) =>
        selectRecurring.insertAdjacentHTML("beforeend", `<option value="${c.id}">${c.nome}</option>`)
      );
    }
  } catch (e) {
    console.error("Erro ao carregar categorias:", e);
  }
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
  renderCards(loadMonthData);
  renderCardOptions();
  renderPurchaseFilters();
  renderPurchaseTable(loadMonthData);
  renderRecurringTable(loadMonthData);
};

export const loadMonthData = async () => {
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

export const handlePurchaseSubmit = async (event) => {
  event.preventDefault();
  const form = event.target;

  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }

  const tipoPagamentoInput = document.querySelector('input[name="tipo_pagamento"]:checked');
  const tipoPagamento = tipoPagamentoInput ? tipoPagamentoInput.value : "CREDITO";
  const newCatName = document.getElementById("purchaseNewCategory").value;
  const catId = document.getElementById("purchaseCategory").value;

  const payload = {
    cartao_id: tipoPagamento === "CREDITO" ? Number(elements.purchaseCard.value) : null,
    tipo_pagamento: tipoPagamento,
    descricao: elements.purchaseDescription.value.trim(),
    valor_total: Number(elements.purchaseTotal.value),
    parcelas: tipoPagamento === "CREDITO" ? Number(elements.purchaseInstallments.value) : 1,
    primeiro_vencimento: elements.purchaseFirstDue.value,
    categoria: catId ? Number(catId) : null,
    nova_categoria: newCatName || null,
  };

  if (payload.tipo_pagamento === "CREDITO" && !payload.cartao_id) {
    showToast("Selecione um cartão válido para compras no crédito.", "danger");
    return;
  }

  const tempId = `temp-${Date.now()}`;

  let displayCardName = "";
  if (payload.cartao_id) {
    displayCardName = elements.purchaseCard.selectedOptions[0]?.textContent || "Cartão";
  } else {
    displayCardName = payload.tipo_pagamento;
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
  renderPurchaseTable(loadMonthData);

  try {
    await apiFetch("/api/card-purchase/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    showToast("Compra adicionada.");

    form.reset();
    form.classList.remove("was-validated");

    const newCatInput = document.getElementById("purchaseNewCategory");
    const catSelect = document.getElementById("purchaseCategory");
    const toggleBtn = document.getElementById("btnToggleNewCat");

    if (newCatInput) newCatInput.style.display = "none";
    if (catSelect) catSelect.style.display = "block";
    if (toggleBtn) toggleBtn.textContent = "+";

    const creditRadio = document.getElementById("typeCredit");
    if (creditRadio) {
      creditRadio.checked = true;
      creditRadio.dispatchEvent(new Event("change"));
    }

    bootstrap.Modal.getInstance(document.getElementById("purchaseModal"))?.hide();

    await loadMonthData();
    if (payload.nova_categoria) {
      loadCategories();
    }
  } catch (error) {
    appState.data.purchases = appState.data.purchases.filter((item) => item.id !== tempId);
    renderPurchaseTable(loadMonthData);
    showToast(`Erro ao salvar compra: ${error.message}`, "danger");
  }
};

export const handleRecurringSubmit = async (event) => {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }

  const recurringId = form.dataset.recurringId;
  const newCatName = document.getElementById("recurringNewCategory").value;
  const catId = document.getElementById("recurringCategory").value;

  const payload = {
    descricao: elements.recurringDescription.value.trim(),
    valor: Number(elements.recurringValue.value),
    dia_vencimento: Number(elements.recurringDay.value),
    inicio: elements.recurringStart.value,
    fim: elements.recurringEnd.value || null,
    ativo: elements.recurringActive.checked,
    categoria: catId ? Number(catId) : null,
    nova_categoria: newCatName || null,
  };

  try {
    if (recurringId) {
      await apiFetch(`/api/recurring-expense/${recurringId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      showToast("Recorrência atualizada.");
    } else {
      await apiFetch("/api/recurring-expense/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Recorrência adicionada.");
    }
    form.reset();
    form.classList.remove("was-validated");

    document.getElementById("recurringNewCategory").style.display = "none";
    document.getElementById("recurringCategory").style.display = "block";
    const btn = document.getElementById("btnToggleNewCatRecurring");
    if (btn) btn.textContent = "+";

    delete form.dataset.recurringId;
    const title = document.getElementById("recurringModalLabel");
    if (title) title.textContent = "Nova recorrência";
    const submitButton = document.querySelector('button[type="submit"][form="recurringForm"]');
    if (submitButton) submitButton.textContent = "Salvar recorrência";

    bootstrap.Modal.getInstance(document.getElementById("recurringModal"))?.hide();
    await loadMonthData();
    if (payload.nova_categoria) loadCategories();
  } catch (error) {
    showToast(`Erro ao salvar recorrência: ${error.message}`, "danger");
  }
};

export const bindEvents = () => {
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
    renderPurchaseTable(loadMonthData);
  });
  elements.purchaseCardFilter.addEventListener("change", (event) => {
    appState.filters.purchaseCard = event.target.value;
    renderPurchaseTable(loadMonthData);
  });
  elements.purchaseTypeFilter.addEventListener("change", (event) => {
    appState.filters.purchaseType = event.target.value;
    renderPurchaseTable(loadMonthData);
  });
  elements.purchaseSort.addEventListener("change", (event) => {
    appState.filters.purchaseSort = event.target.value;
    renderPurchaseTable(loadMonthData);
  });

  elements.recurringSearch.addEventListener("input", (event) => {
    appState.filters.recurringSearch = event.target.value;
    renderRecurringTable(loadMonthData);
  });
  elements.recurringSort.addEventListener("change", (event) => {
    appState.filters.recurringSort = event.target.value;
    renderRecurringTable(loadMonthData);
  });

  document.getElementById("purchaseForm")?.addEventListener("submit", handlePurchaseSubmit);
  document.getElementById("recurringForm")?.addEventListener("submit", handleRecurringSubmit);

  const btnToggleCatRec = document.getElementById("btnToggleNewCatRecurring");
  if (btnToggleCatRec) {
    btnToggleCatRec.addEventListener("click", () => {
      const select = document.getElementById("recurringCategory");
      const input = document.getElementById("recurringNewCategory");
      if (input.style.display === "none") {
        input.style.display = "block";
        select.style.display = "none";
        input.focus();
        btnToggleCatRec.textContent = "x";
      } else {
        input.style.display = "none";
        select.style.display = "block";
        input.value = "";
        btnToggleCatRec.textContent = "+";
      }
    });
  }

  document.getElementById("recurringModal")?.addEventListener("shown.bs.modal", () => {
    const inputCat = document.getElementById("recurringNewCategory");
    const selectCat = document.getElementById("recurringCategory");
    const btnCat = document.getElementById("btnToggleNewCatRecurring");
    if (inputCat) {
      inputCat.style.display = "none";
      inputCat.value = "";
    }
    if (selectCat) selectCat.style.display = "block";
    if (btnCat) btnCat.textContent = "+";

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

  const paymentRadios = document.querySelectorAll('input[name="tipo_pagamento"]');
  paymentRadios.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      const type = e.target.value;
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

  const btnToggleCat = document.getElementById("btnToggleNewCat");
  if (btnToggleCat) {
    btnToggleCat.addEventListener("click", () => {
      const select = document.getElementById("purchaseCategory");
      const input = document.getElementById("purchaseNewCategory");

      if (input.style.display === "none") {
        input.style.display = "block";
        select.style.display = "none";
        input.focus();
        btnToggleCat.textContent = "x";
      } else {
        input.style.display = "none";
        select.style.display = "block";
        input.value = "";
        btnToggleCat.textContent = "+";
      }
    });
  }

  document.getElementById("purchaseModal")?.addEventListener("show.bs.modal", (event) => {
    const creditRadio = document.getElementById("typeCredit");
    if (creditRadio) {
      creditRadio.checked = true;
      creditRadio.dispatchEvent(new Event("change"));
    }

    const inputCat = document.getElementById("purchaseNewCategory");
    const selectCat = document.getElementById("purchaseCategory");
    const btnCat = document.getElementById("btnToggleNewCat");
    if (inputCat) {
      inputCat.style.display = "none";
      inputCat.value = "";
    }
    if (selectCat) selectCat.style.display = "block";
    if (btnCat) btnCat.textContent = "+";

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

    if (elements.purchaseDescription) {
      elements.purchaseDescription.focus();
    }
  });

  document.getElementById("recurringModal")?.addEventListener("shown.bs.modal", () => {
    elements.recurringDescription.focus();
  });
};

export const init = () => {
  updateLogsPendingBadge();
  initSystemLogs();



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
