import { appState, elements } from "./state.js";
import { apiFetch } from "./api.js";
import { formatCurrency, formatDate, showToast } from "./utils.js";
import { createEditableCell, getCardBadgeVariant, openConfirmDelete, setLoadingState } from "./ui.js";

let reloadMonthData = null;

const setReloadMonthData = (callback) => {
  if (typeof callback === "function") {
    reloadMonthData = callback;
  }
};

const applyPurchaseFilters = (purchases) => {
  const search = appState.filters.purchaseSearch.toLowerCase();
  return purchases
    .filter((item) => item.descricao.toLowerCase().includes(search))
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

export const renderSummary = () => {
  const { totals } = appState.data;
  elements.totalMonth.textContent = formatCurrency(totals.total_month || 0);
  elements.totalCard.textContent = formatCurrency(totals.total_card || 0);
  elements.totalRecurring.textContent = formatCurrency(totals.total_recurring || 0);
};

export const updatePurchaseCard = async (purchaseId, newCardId, newCardName) => {
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
    await reloadMonthData?.();
  } catch (error) {
    Object.assign(purchase, previous);
    renderPurchaseTable();
    showToast(`Erro ao mover compra: ${error.message}`, "danger");
  }
};

export const renderCards = (reloadCallback) => {
  setReloadMonthData(reloadCallback);
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

export const renderPurchaseTable = (reloadCallback) => {
  setReloadMonthData(reloadCallback);
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
    const dueEditable = createEditableCell(
      formatDate(item.primeiro_vencimento),
      "date",
      item.primeiro_vencimento
    );
    dueCell.appendChild(dueEditable.wrapper);

    const valueCell = document.createElement("td");
    valueCell.className = "text-end";
    const valueEditable = createEditableCell(
      formatCurrency(item.valor_parcela),
      "number",
      item.valor_total,
      "form-control form-control-sm text-end"
    );
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
          await reloadMonthData?.();
        } catch (error) {
          Object.assign(item, previous);
          renderPurchaseTable();
          showToast(`Erro ao atualizar compra: ${error.message}`, "danger");
        }
      }
      if (action === "delete") {
        openConfirmDelete(`Excluir compra "${item.descricao}"?`, async () => {
          const previousData = [...appState.data.purchases];
          appState.data.purchases = appState.data.purchases.filter(
            (purchase) => purchase.id !== item.id
          );
          renderPurchaseTable();
          try {
            await apiFetch(`/api/card-purchase/${item.id}/`, { method: "DELETE" });
            showToast("Compra excluída.");
            await reloadMonthData?.();
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

export const markRecurringAsPaid = async (id) => {
  if (!confirm("Confirmar pagamento desta conta?")) return;

  setLoadingState(true);
  try {
    const payload = {
      year: appState.year,
      month: appState.month,
    };

    await apiFetch(`/api/recurring/${id}/pay/`, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    showToast("Conta marcada como paga!", "success");
    await reloadMonthData?.();
  } catch (error) {
    showToast(`Erro: ${error.message}`, "danger");
  } finally {
    setLoadingState(false);
  }
};

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

export const renderRecurringTable = (reloadCallback) => {
  setReloadMonthData(reloadCallback);
  const tbody = document.querySelector("#recurringTable tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const filtered = applyRecurringFilters(appState.data.recurring || []);

  filtered.forEach((r) => {
    const tr = document.createElement("tr");
    tr.dataset.id = r.id;
    if (!r.ativo) tr.classList.add("text-muted", "bg-light");

    const dayCell = document.createElement("td");
    dayCell.textContent = r.dia_vencimento;
    tr.appendChild(dayCell);

    const descCell = document.createElement("td");
    descCell.innerHTML = `<div class="fw-medium">${r.descricao}</div><small class="text-muted">Desde ${new Date(
      r.inicio
    ).toLocaleDateString("pt-BR")}</small>`;
    tr.appendChild(descCell);

    const categoryCell = document.createElement("td");
    categoryCell.innerHTML = r.categoria_nome
      ? `<span class="badge bg-secondary">${r.categoria_nome}</span>`
      : '<span class="text-muted">Sem categoria</span>';
    tr.appendChild(categoryCell);

    const valCell = document.createElement("td");
    valCell.innerHTML = `<span class="blur-sensitive">${formatCurrency(r.valor)}</span>`;
    tr.appendChild(valCell);

    const statusCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    statusBadge.className = `badge ${
      r.ativo ? (r.is_paid ? "bg-success" : "bg-warning text-dark") : "bg-secondary"
    }`;
    statusBadge.textContent = r.ativo ? (r.is_paid ? "Pago" : "Pendente") : "Inativo";
    statusCell.appendChild(statusBadge);
    tr.appendChild(statusCell);

    const actCell = document.createElement("td");
    actCell.className = "text-end";

    if (r.ativo) {
      const editBtn = document.createElement("button");
      editBtn.className = "btn btn-sm btn-outline-secondary me-2";
      editBtn.innerHTML = '<i class="bi bi-pencil"></i>';
      editBtn.title = "Editar recorrência";
      editBtn.onclick = () => openRecurringEditModal(r);
      actCell.appendChild(editBtn);

      if (!r.is_paid) {
        const payBtn = document.createElement("button");
        payBtn.className = "btn btn-sm btn-outline-success me-2";
        payBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
        payBtn.title = "Marcar como Pago";
        payBtn.onclick = () => markRecurringAsPaid(r.id);
        actCell.appendChild(payBtn);
      } else {
        const paidBadge = document.createElement("span");
        paidBadge.className = "badge bg-success me-2";
        paidBadge.innerText = "Pago";
        actCell.appendChild(paidBadge);
      }
    }

    const delBtn = document.createElement("button");
    delBtn.className = "btn btn-sm btn-link text-danger p-0";
    delBtn.innerHTML = '<i class="bi bi-trash"></i>';
    if (typeof window.deleteRecurring === "function") {
      delBtn.onclick = () => window.deleteRecurring(r.id);
    } else {
      delBtn.onclick = () => console.log("Função deleteRecurring não encontrada");
    }

    actCell.appendChild(delBtn);

    tr.appendChild(actCell);

    tbody.appendChild(tr);
  });
};
