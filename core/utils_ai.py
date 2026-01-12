import os
import json
from openai import OpenAI
from datetime import date
from django.conf import settings
import re


def analyze_invoice_text(text_content):
    """
    Envia o texto para o OpenAI e retorna uma lista estruturada de despesas.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("ERRO: OPENAI_API_KEY não encontrada no .env")
        return []

    client = OpenAI(api_key=api_key)
    today = date.today()
    current_year = today.year

    print(f"--- DEBUG AI: Iniciando análise de texto ({len(text_content)} chars) ---")

    prompt = f"""
    Aja como um extrator de dados financeiros. Analise o texto abaixo, que veio de uma fatura de cartão.

    REGRAS DE INTERPRETAÇÃO:
    1. Muitas linhas começam com um código numérico antes da data:
       - Se começar com "2", é uma compra ONLINE.
       - Se começar com "3", é uma compra FÍSICA (Loja).
    2. O ano atual é {current_year}. Formate datas como YYYY-MM-DD.
    3. Ignore linhas que sejam apenas pagamentos de fatura ou saldos.
    4. Regra de parcelas: Se houver algo como "NN/MM" no final da linha e
       já existir outra data na linha (DD/MM), trate "NN/MM" como parcela
       (ex: 09/12 = parcela 9 de 12). Use o total de parcelas = 12.
    5. Se houver parcelas (ex: "02/10"), extraia o total de parcelas.
    6. Converta valores para float (ex: 59,90 vira 59.90).

    TEXTO BRUTO:
    {text_content}

    SAÍDA ESPERADA (JSON puro, sem markdown):
    Uma lista de objetos com chaves: "data", "descricao", "valor", "parcelas" (int, default 1), "tipo_compra" (string: "Online", "Física" ou "Indefinido").
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        content = response.choices[0].message.content

        # Limpeza caso a IA devolva blocos de código
        if "```" in content:
            content = content.replace("```json", "").replace("```", "")

        data = json.loads(content)

        date_pattern = re.compile(r"^(?P<day>\d{1,2})/(?P<month>\d{1,2})(?:/(?P<year>\d{2,4}))?$")

        for item in data:
            parcelas = item.get("parcelas", 1)
            try:
                parcelas = int(parcelas)
            except (TypeError, ValueError):
                parcelas = 1
            item["parcelas"] = parcelas if parcelas > 0 else 1

            raw_date = item.get("data")
            if not raw_date:
                continue

            parsed_date = None
            try:
                parsed_date = date.fromisoformat(raw_date)
            except ValueError:
                match = date_pattern.match(str(raw_date).strip())
                if match:
                    day = int(match.group("day"))
                    month = int(match.group("month"))
                    year = match.group("year")
                    year = int(year) if year else current_year
                    if year < 100:
                        year += 2000
                    parsed_date = date(year, month, day)
            if not parsed_date:
                continue

            if parsed_date.year > current_year:
                parsed_date = date(current_year, parsed_date.month, parsed_date.day)

            if parsed_date > today:
                adjusted_date = date(parsed_date.year - 1, parsed_date.month, parsed_date.day)
                item["data"] = adjusted_date.isoformat()
            else:
                item["data"] = parsed_date.isoformat()

        print(f"--- DEBUG AI: Sucesso! {len(data)} itens extraídos. ---")
        return data

    except Exception as e:
        print(f"--- DEBUG AI ERRO: {e} ---")
        return []
