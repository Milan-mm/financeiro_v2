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
