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

// 3. Renderizar Tabela (Preview)
const renderImportTable = async () => {
    const tbody = document.getElementById('importTableBody');
    tbody.innerHTML = '';

    // Precisamos garantir que temos categorias
    let categories = appState.categories || [];
    if (categories.length === 0) {
        categories = await apiFetch('/api/categories/'); // Fallback se não tiver no state
    }
    const catOptions = categories.map(c => `<option value="${c.id}">${c.nome}</option>`).join('');

    importedItems.forEach((item, index) => {
        const tr = document.createElement('tr');

        let badgeClass = "bg-secondary";
        if (item.tipo_compra === "Online") badgeClass = "bg-info";
        if (item.tipo_compra === "Física") badgeClass = "bg-warning text-dark";

        tr.innerHTML = `
            <td><input type="date" class="form-control form-control-sm" value="${item.data}" id="imp-date-${index}"></td>
            <td>
                <input type="text" class="form-control form-control-sm mb-1" value="${item.descricao}" id="imp-desc-${index}">
                <span class="badge ${badgeClass}" style="font-size:0.7em">${item.tipo_compra || '?'}</span>
            </td>
             <td>
                <span class="badge bg-light text-dark border">x${item.parcelas}</span>
            </td>
            <td>
                <input type="number" step="0.01" class="form-control form-control-sm" value="${item.valor}" id="imp-val-${index}">
            </td>
            <td>
                <select class="form-select form-select-sm" id="imp-cat-${index}">
                    <option value="">Sem Categoria</option>
                    ${catOptions}
                </select>
            </td>
            <td class="text-end">
                <button class="btn btn-sm text-danger btn-remove-item" data-index="${index}"><i class="bi bi-x-lg"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Adiciona evento de remover dinamicamente (pois os botões acabaram de ser criados)
    document.querySelectorAll('.btn-remove-item').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = e.target.closest('button').dataset.index;
            removeImportItem(idx);
        });
    });
};

const removeImportItem = (index) => {
    importedItems.splice(index, 1);
    renderImportTable();
};

// 4. Salvar Lote
const saveImportBatch = async () => {
    const cardId = document.getElementById('importCardSelect').value;
    if (!cardId) return alert("Por favor, selecione o cartão.");

    const finalItems = importedItems.map((_, index) => ({
        data: document.getElementById(`imp-date-${index}`).value,
        descricao: document.getElementById(`imp-desc-${index}`).value,
        valor: parseFloat(document.getElementById(`imp-val-${index}`).value),
        parcelas: importedItems[index].parcelas,
        category_id: document.getElementById(`imp-cat-${index}`).value
    }));

    setLoadingState(true);
    try {
        const result = await apiFetch('/api/import/save/', {
            method: 'POST',
            body: JSON.stringify({
                card_id: cardId,
                items: finalItems
            })
        });

        showToast(`${result.count} compras importadas!`);

        // Fecha o modal (Bootstrap)
        const modalEl = document.getElementById('importModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();

        resetImportModal();

        // Atualiza a Dashboard
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
};