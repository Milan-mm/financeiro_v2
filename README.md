# Financeiro v2 (Django)

## Development setup

### 1) Python environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Environment variables
```bash
cp .env.example .env.development
```
Update values as needed.

### 3) Database
```bash
python manage.py migrate
```

### 4) Tailwind CSS
```bash
npm install
npm run build:css
# or for watch mode:
# npm run watch:css
```
Tailwind output is generated locally at `static/css/tailwind.css` and is not committed to git.

### 5) Bootstrap household
```bash
python manage.py bootstrap_household --household-name "Home" --users user1,user2
```

### 6) Run server
```bash
python manage.py runserver
```

## Notes
- Tailwind output is generated at `static/css/tailwind.css`.
- HTMX is loaded in the base template for partial updates.

## Statement attribution rule (credit card)
When importing or attributing credit card purchases to a statement, the system follows:
- **Year inference:** for each `DD/MM` purchase line, if `line_month > statement_month` then `inferred_year = statement_year - 1`; otherwise `inferred_year = statement_year`. This keeps statement-month context even when the purchase date is from a prior year.
- **Ledger date:** card statement charges are recorded with `ledger_date = closing_date` of the statement month. This ensures the charge appears in the statement month (closing month), regardless of the original purchase date.
- **Installments:** when a line includes `current/total` (e.g. `09/12`), the import generates installments starting at the current number through the total, and the first generated installment is attributed to the selected statement month.

## README técnico - Importação de faturas (diagnóstico e proposta)

### Escopo analisado
Fluxo atual de importação de faturas via texto colado no formulário (sem OCR) e geração de parcelas. Fontes relevantes:

- Parsing do texto da fatura em itens estruturados: `finance/statement_importer.py`.
- Criação de `ImportBatch` e `ImportItem`: `finance/views.py` + `finance/services.py`.
- Geração de grupos de compra parcelada e parcelas: `finance/views.py` + `finance/services.py`.
- Estrutura de dados persistida: `finance/models.py`.

### Como o texto é normalizado hoje
O parser é determinístico e usa regex:

- Remove linhas de cabeçalho e ignora linhas sem data (ex.: “Compra Data Descrição”).
- Extrai a data (`DD/MM`) e infere o ano com base no mês da fatura.
- Extrai o primeiro marcador `NN/NN` de parcelas com `total > 1`.
- Extrai valores monetários e escolhe o último (ou penúltimo quando há valor em dólar) como valor da parcela.
- Normaliza a descrição removendo marcadores de parcela e valores, colapsando espaços duplicados.
- Define um `flag` de compra (ONLINE/APPROX/UNKNOWN) com base no prefixo numérico da linha.

### Como compras parceladas são identificadas hoje
- Um item é considerado parcelado quando o parser encontra `installments_current` e `installments_total` (ex.: `03/12`).
- No momento da confirmação da importação:
  - Cria-se um `CardPurchaseGroup` para cada item (mesmo que já exista outro grupo equivalente).
  - `total_amount` é calculado como `amount * installments_total`.
  - `generate_installments_from_statement` cria parcelas do número **corrente** até o total, com lançamentos em meses futuros.

### Campos atualmente usados como “chave lógica”
Não existe chave lógica/heurística de deduplicação no fluxo atual. Cada item importado resulta em um novo grupo e novas parcelas.

### Onde ocorre a duplicidade (ponto exato)
A duplicidade acontece em `import_confirm` (finance/views.py): para cada `ImportItem` confirmada, sempre é criado um novo `CardPurchaseGroup` e novas `Installment` (finance/services.py), sem buscar grupos existentes com a mesma compra “mãe”.

Em faturas subsequentes, quando a mesma compra reaparece apenas com `installments_current` diferente, o fluxo cria outro grupo e gera parcelas duplicadas, porque:

- `purchase_date`, `description` e `amount` são iguais à compra original;
- `installments_current` muda (ex.: `02/04` → `03/04`), mas isso não é usado para vincular a um grupo existente;
- não há verificação por descrição normalizada, data de origem, valor e total de parcelas.

### Implementação (Sprint 1)
- Compras parceladas passam a gerar uma `logical_key` determinística (`description` normalizada + `purchase_date` + `amount` + `installments_total`). Essa chave é persistida no grupo e usada para reaproveitar o “grupo compra-mãe” em importações subsequentes.
- A criação de parcelas via importação agora é idempotente e cria apenas a parcela correspondente ao mês importado (não gera parcelas futuras automaticamente).
- O match é determinístico e depende da descrição normalizada; variações relevantes de descrição podem exigir uma normalização mais robusta em um sprint futuro.

### Riscos atuais do modelo de importação
- **Duplicação de lançamentos:** cada nova fatura reimporta parcelas já existentes e cria grupos paralelos.
- **Quebra de rastreabilidade:** parcelas iguais ficam em grupos diferentes sem vínculo claro.
- **Validação ambígua:** sem chave lógica, não há como garantir idempotência entre meses.
- **Correções manuais difíceis:** o usuário precisa identificar e remover duplicadas manualmente.

### Sugestões de estratégia para impedir duplicadas
Abaixo estão abordagens possíveis. A implementação futura deve considerar migração segura e versionamento do modelo.

#### 1) Chave lógica composta (determinística)
**Ideia:** gerar um `logical_key` para identificar a compra-mãe, usando:

```
(description_normalized + purchase_date + amount + installments_total)
```

**Como usar:**
- Persistir `logical_key` em `CardPurchaseGroup` e em `ImportItem`.
- Na importação, buscar grupo existente com a mesma chave antes de criar um novo.

**Prós**
- Simples de implementar e entender.
- Fácil de auditar (chave reproduzível a partir do texto).

**Contras**
- Sensível a variações de descrição (ex.: “LATAM AIR” vs “LATAM AIR *123”).
- Pode confundir compras distintas com mesmos valores e datas iguais.

#### 2) Identificador de “compra-mãe” (grupo persistente)
**Ideia:** criar o grupo uma única vez e anexar parcelas subsequentes ao mesmo grupo.

**Como usar:**
- No import, tentar localizar grupo pelo conjunto de atributos equivalentes e anexar a parcela corrente.
- Opcional: armazenar `purchase_fingerprint` com tokens da descrição e total de parcelas.

**Prós**
- Melhora rastreabilidade e consolida parcelas.
- Permite controle de idempotência por grupo + número da parcela.

**Contras**
- Requer lógica de match/merge e possíveis correções históricas.
- Pode exigir migração de dados existentes para evitar duplicidade retroativa.

#### 3) Heurísticas tolerantes a variação de descrição
**Ideia:** normalizar descrição de forma robusta (remove sufixos variáveis, tokens numéricos não relevantes).

Exemplos de normalização:
- Remover padrões de voucher/cartão (`*1234`, `#123`), IDs longos, múltiplos espaços.
- Uppercase + remoção de diacríticos.
- Tokenização e comparação por similaridade (ex.: Jaccard) acima de um limiar.

**Prós**
- Reduz falsos negativos em comerciantes com descrições dinâmicas.
- Ajuda a agrupar compras recorrentes/parceladas corretamente.

**Contras**
- Aumenta risco de falsos positivos (compras diferentes com descrições parecidas).
- Pode exigir ajustes por cartão/banco.

#### 4) Estratégia de idempotência por fatura (importação mensal)
**Ideia:** garantir que importar a mesma fatura (ou faturas subsequentes) não gere duplicatas.

Possíveis estratégias:
- Armazenar `statement_id` (hash do texto + mês/ano + cartão) e bloquear reimportação.
- Para cada import, registrar as parcelas criadas e bloquear re-criação pelo par (`group_id`, `installment_number`).
- Marcar parcelas já existentes com base no mês da fatura e `installments_current`.

**Prós**
- Evita duplicação acidental de reimportação do mesmo texto.
- Atua como “última linha de defesa” contra duplicidade.

**Contras**
- Não resolve por si só a identificação de compra-mãe.
- Pode bloquear casos legítimos de correção quando a fatura mudou.

### Recomendações para patch futuro (alto nível)
1. **Definir e persistir uma chave lógica** (descrição normalizada + data de origem + valor + total de parcelas).
2. **Buscar grupo existente** antes de criar um novo `CardPurchaseGroup`.
3. **Garantir idempotência** na criação de parcelas (ex.: unique constraint em `group + number` já existe, mas precisa ser respeitada no fluxo).
4. **Planejar migração**:
   - criar script para identificar grupos duplicados por chave lógica;
   - revisar manualmente os casos ambíguos.

### Observações sobre o uso de IA
Apesar de o produto ser descrito como “importação via IA”, o parser atualmente é regex-based e determinístico. Caso a IA volte a ser usada no futuro, as mesmas regras de chave lógica e idempotência devem ser aplicadas ao payload final antes de criar grupos e parcelas.
