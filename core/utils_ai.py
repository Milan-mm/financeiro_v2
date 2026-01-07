import os
import json
from openai import OpenAI
from datetime import date
from django.conf import settings


def analyze_invoice_text(text_content):
    """
    Envia o texto para o OpenAI e retorna uma lista estruturada de despesas.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("ERRO: OPENAI_API_KEY não encontrada no .env")
        return []

    client = OpenAI(api_key=api_key)
    current_year = date.today().year

    print(f"--- DEBUG AI: Iniciando análise de texto ({len(text_content)} chars) ---")

    prompt = f"""
    Aja como um extrator de dados financeiros. Analise o texto abaixo, que veio de uma fatura de cartão.

    REGRAS DE INTERPRETAÇÃO:
    1. Muitas linhas começam com um código numérico antes da data:
       - Se começar com "2", é uma compra ONLINE.
       - Se começar com "3", é uma compra FÍSICA (Loja).
    2. O ano atual é {current_year}. Formate datas como YYYY-MM-DD.
    3. Ignore linhas que sejam apenas pagamentos de fatura ou saldos.
    4. Se houver parcelas (ex: "02/10"), extraia o total de parcelas.
    5. Converta valores para float (ex: 59,90 vira 59.90).

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

        # --- AJUSTE FORÇADO DE DATA ---
        # Sobrescreve a data original da compra pela data de hoje.
        # Isso garante que a compra entre na dashboard/fatura atual,
        # independentemente de quando ela foi feita no passado.
        today_iso = date.today().isoformat()

        for item in data:
            item["data"] = today_iso
        # ------------------------------

        print(f"--- DEBUG AI: Sucesso! {len(data)} itens extraídos. (Todas as datas forçadas para {today_iso}) ---")
        return data

    except Exception as e:
        print(f"--- DEBUG AI ERRO: {e} ---")
        return []