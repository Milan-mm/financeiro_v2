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
