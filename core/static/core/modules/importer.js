// core/static/core/modules/importer.js
import { apiFetch } from './api.js';
import { showToast } from './utils.js';
import { appState } from './state.js';
import { setLoadingState } from './ui.js';

let importedItems = [];
let refreshDashboardCallback = null; // Função para recarregar a tela

// 1. Função Inicial para ligar os botões
export const initImporter = (refreshCallback) => {
    refreshDashboardCallback = refreshCallback;

    // Ligar o botão "Analisar"
    const btnAnalyze = document.getElementById('btnAnalyzeImport');
    if (btnAnalyze) {
        btnAnalyze.addEventListener('click', analyzeImportText);
    }

    // Ligar o botão "Confirmar"
    const btnSave = document.getElementById('btnSaveImport');
    if (btnSave) {
        btnSave.addEventListener('click', saveImportBatch);
    }

    // Ligar o botão "Voltar" (Reset)
    const btnReset = document.getElementById('btnResetImport');
    if (btnReset) {
        btnReset.addEventListener('click', resetImportModal);
    }

    const overrideCheckbox = document.getElementById('importOverrideToday');
    if (overrideCheckbox) {
        overrideCheckbox.addEventListener('change', applyOverrideDates);
    }
};

const applyOverrideDates = () => {
    const overrideCheckbox = document.getElementById('importOverrideToday');
    if (!overrideCheckbox) return;
    const useToday = overrideCheckbox.checked;
    const todayIso = new Date().toISOString().slice(0, 10);

    importedItems.forEach((item, index) => {
        const input = document.getElementById(`imp-date-${index}`);
        if (!input) return;
        input.value = useToday ? todayIso : item.data;
    });
};

// 2. Análise (Envia para o Django/GPT)
const analyzeImportText = async () => {
    const textInput = document.getElementById('importText');
    const text = textInput.value;

    if (!text.trim()) return alert("Cole algum texto da fatura primeiro.");

    // UI Updates
    document.getElementById('stepPaste').classList.add('d-none');
    document.getElementById('importLoading').classList.remove('d-none');

    try {
        const data = await apiFetch('/api/import/parse/', {
            method: 'POST',
            body: JSON.stringify({ text: text })
        });

        importedItems = data;
        await renderImportTable();

        // Popula o select de cartões
        const cardSelect = document.getElementById('importCardSelect');
        cardSelect.innerHTML = '<option value="">Selecione o Cartão...</option>';
        appState.data.cards.forEach(c => {
            cardSelect.innerHTML += `<option value="${c.id}">${c.nome}</option>`;
        });

        // Mostra a revisão
        document.getElementById('importLoading').classList.add('d-none');
        document.getElementById('stepReview').classList.remove('d-none');

    } catch (error) {
        showToast("Erro na análise: " + error.message, "danger");
        resetImportModal();
    }
};
// 3. Renderizar Tabela (Preview) com suporte a Nova Categoria
const renderImportTable = async () => {
    const tbody = document.getElementById('importTableBody');
    tbody.innerHTML = '';

    let categories = appState.categories || [];
    if (categories.length === 0) {
        categories = await apiFetch('/api/categories/');
        appState.categories = categories;
    }
    const catOptions = categories.map(c => `<option value="${c.id}">${c.nome}</option>`).join('');

    importedItems.forEach((item, index) => {
        const tr = document.createElement('tr');
        if (item.is_duplicate) {
            tr.classList.add('table-danger');
        }

        let badgeClass = "bg-secondary";
        if (item.tipo_compra === "Online") badgeClass = "bg-info";
        if (item.tipo_compra === "Física") badgeClass = "bg-warning text-dark";

        // Adicionamos a estrutura de Toggle na coluna de Categoria (coluna 5)
        const duplicateBadge = item.is_duplicate
            ? '<span class="badge bg-danger ms-1" style="font-size:0.7em">Duplicada</span>'
            : '';

        tr.innerHTML = `
            <td><input type="date" class="form-control form-control-sm" value="${item.data}" id="imp-date-${index}"></td>
            <td>
                <input type="text" class="form-control form-control-sm mb-1" value="${item.descricao}" id="imp-desc-${index}">
                <span class="badge ${badgeClass}" style="font-size:0.7em">${item.tipo_compra || '?'}</span>
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
                <button class="btn btn-sm text-danger btn-remove-item" data-index="${index}"><i class="bi bi-x-lg"></i></button>
            </td>
        `;
        tbody.appendChild(tr);

        // Recupera seleção anterior se houver
        if (item.category_id) {
            const sel = document.getElementById(`imp-cat-${index}`);
            if(sel) sel.value = item.category_id;
        }
    });

    document.querySelectorAll('.add-cat-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = Number(e.currentTarget.dataset.index);
            appState.importer.pendingCategoryIndex = idx;
            const modalElement = document.getElementById('categoryModal');
            if (modalElement) {
                bootstrap.Modal.getOrCreateInstance(modalElement).show();
            }
        });
    });

    // Lógica Remover
    document.querySelectorAll('.btn-remove-item').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = e.target.closest('button').dataset.index;
            removeImportItem(idx);
        });
    });

    applyOverrideDates();
};

// 4. Salvar Lote (Atualizado para ler o input de nova categoria)
const saveImportBatch = async () => {
    const cardId = document.getElementById('importCardSelect').value;
    const overrideToday = Boolean(document.getElementById('importOverrideToday')?.checked);
    if (!cardId) return alert("Por favor, selecione o cartão.");

    const finalItems = importedItems.map((_, index) => {
        const catSelect = document.getElementById(`imp-cat-${index}`);
        const catId = catSelect ? catSelect.value : null;

        return {
            data: document.getElementById(`imp-date-${index}`).value,
            descricao: document.getElementById(`imp-desc-${index}`).value,
            valor: parseFloat(document.getElementById(`imp-val-${index}`).value),
            parcelas: importedItems[index].parcelas,
            category_id: catId
        };
    });

    setLoadingState(true);
    try {
        const result = await apiFetch('/api/import/save/', {
            method: 'POST',
            body: JSON.stringify({
                card_id: cardId,
                override_today: overrideToday,
                items: finalItems
            })
        });

        showToast(`${result.count} compras importadas!`);

        const modalEl = document.getElementById('importModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();

        resetImportModal();

        // Força recarregar categorias caso tenhamos criado novas
        // O app.js provavelmente tem essa função exportada ou acessível
        // Se não tiver, o refreshDashboard vai acabar carregando eventualmente
        if (appState.categories) appState.categories = []; // Limpa cache local

        if (refreshDashboardCallback) refreshDashboardCallback();

    } catch (error) {
        showToast("Erro ao salvar: " + error.message, "danger");
    } finally {
        setLoadingState(false);
    }
};

const resetImportModal = () => {
    document.getElementById('stepPaste').classList.remove('d-none');
    document.getElementById('stepReview').classList.add('d-none');
    document.getElementById('importLoading').classList.add('d-none');
    document.getElementById('importText').value = '';
    importedItems = [];
    appState.importer.pendingCategoryIndex = null;
    const overrideCheckbox = document.getElementById('importOverrideToday');
    if (overrideCheckbox) overrideCheckbox.checked = false;
};
