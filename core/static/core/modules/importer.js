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

        let badgeClass = "bg-secondary";
        if (item.tipo_compra === "Online") badgeClass = "bg-info";
        if (item.tipo_compra === "Física") badgeClass = "bg-warning text-dark";

        // Adicionamos a estrutura de Toggle na coluna de Categoria (coluna 5)
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
                <div class="d-flex align-items-center">
                    <select class="form-select form-select-sm" id="imp-cat-${index}" style="display: block;">
                        <option value="">Sem Categoria</option>
                        ${catOptions}
                    </select>
                    
                    <input type="text" class="form-control form-control-sm" id="imp-new-cat-${index}" 
                           placeholder="Nova categoria..." style="display: none;">
                    
                    <button class="btn btn-sm btn-outline-secondary ms-1 btn-toggle-cat" 
                            type="button" data-index="${index}" title="Criar nova categoria">
                        <i class="bi bi-plus-lg"></i>
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

    // Lógica dos Botões Toggle (+ / x)
    document.querySelectorAll('.btn-toggle-cat').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = e.currentTarget.dataset.index; // currentTarget é mais seguro para botões com ícones
            const select = document.getElementById(`imp-cat-${idx}`);
            const input = document.getElementById(`imp-new-cat-${idx}`);
            const icon = btn.querySelector('i');

            if (input.style.display === 'none') {
                // Modo: Criar Nova
                input.style.display = 'block';
                select.style.display = 'none';
                select.value = ""; // Limpa o select
                input.focus();
                // Troca ícone para X
                btn.classList.replace('btn-outline-secondary', 'btn-outline-danger');
                if(icon) { icon.classList.replace('bi-plus-lg', 'bi-x-lg'); }
            } else {
                // Modo: Selecionar Existente
                input.style.display = 'none';
                select.style.display = 'block';
                input.value = ""; // Limpa o input
                // Troca ícone para +
                btn.classList.replace('btn-outline-danger', 'btn-outline-secondary');
                if(icon) { icon.classList.replace('bi-x-lg', 'bi-plus-lg'); }
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
};

// 4. Salvar Lote (Atualizado para ler o input de nova categoria)
const saveImportBatch = async () => {
    const cardId = document.getElementById('importCardSelect').value;
    if (!cardId) return alert("Por favor, selecione o cartão.");

    const finalItems = importedItems.map((_, index) => {
        const catSelect = document.getElementById(`imp-cat-${index}`);
        const catInput = document.getElementById(`imp-new-cat-${index}`);

        // Se o input estiver visível e preenchido, manda 'nova_categoria'
        // Caso contrário, manda o ID do select
        let catId = null;
        let newCatName = null;

        if (catInput && catInput.style.display !== 'none' && catInput.value.trim() !== "") {
            newCatName = catInput.value.trim();
        } else if (catSelect) {
            catId = catSelect.value;
        }

        return {
            data: document.getElementById(`imp-date-${index}`).value,
            descricao: document.getElementById(`imp-desc-${index}`).value,
            valor: parseFloat(document.getElementById(`imp-val-${index}`).value),
            parcelas: importedItems[index].parcelas,
            category_id: catId,
            nova_categoria: newCatName // Campo novo enviado para o backend
        };
    });

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
};