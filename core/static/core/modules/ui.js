import { appState, elements, monthNames } from "./state.js";

const PRIVACY_STORAGE_KEY = "financeiro:privacy-active";

export const initPrivacyToggle = () => {
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

export const setLoadingState = (isLoading) => {
  if (!isLoading) return;
  elements.purchaseTableBody.innerHTML = `<tr class="skeleton-row"><td colspan="6"><div class="skeleton-line"></div></td></tr>`;
  elements.recurringTableBody.innerHTML = `<tr class="skeleton-row"><td colspan="6"><div class="skeleton-line"></div></td></tr>`;
};

export const populateMonthSelectors = () => {
  elements.monthSelect.innerHTML = monthNames
    .map((name, index) => `<option value="${index + 1}">${name}</option>`)
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

export const updateSelectors = () => {
  elements.monthSelect.value = appState.month;
  elements.yearSelect.value = appState.year;
};

export const openConfirmDelete = (message, onConfirm) => {
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

export const createEditableCell = (
  value,
  inputType,
  inputValue,
  inputClass = "form-control form-control-sm"
) => {
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

export const cardBadgeVariants = [
  "primary",
  "success",
  "info",
  "warning",
  "danger",
  "secondary",
  "dark",
];

export const getCardBadgeVariant = (name) => {
  if (!name) return cardBadgeVariants[0];
  let hash = 0;
  Array.from(name).forEach((char) => {
    hash = (hash + char.charCodeAt(0)) % cardBadgeVariants.length;
  });
  return cardBadgeVariants[hash];
};
