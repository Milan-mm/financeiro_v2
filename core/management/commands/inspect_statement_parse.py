import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.utils_ai import OpenAI
from finance.billing import get_statement_window
from finance.models import Card
from finance.statement_importer import parse_statement_text


class Command(BaseCommand):
    help = "Inspeciona o parsing de uma fatura de cartão e imprime os detalhes."

    def add_arguments(self, parser):
        parser.add_argument("--card", type=int, required=True)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)
        parser.add_argument("--file", type=str)
        parser.add_argument("--text", type=str)
        parser.add_argument("--ai", action="store_true")

    def handle(self, *args, **options):
        card_id = options["card"]
        year = options["year"]
        month = options["month"]
        text = options.get("text")
        file_path = options.get("file")

        if not text and not file_path:
            raise CommandError("Informe --file ou --text.")
        if text and file_path:
            raise CommandError("Use apenas --file ou --text.")

        if file_path:
            text = Path(file_path).read_text(encoding="utf-8")

        card = Card.objects.get(pk=card_id)
        closing_date, period_start, period_end = get_statement_window(year, month, card.closing_day)
        self.stdout.write(f"Cartão: {card.name} (fechamento dia {card.closing_day})")
        self.stdout.write(
            f"Statement {month}/{year} · período {period_start:%d/%m/%Y} a {period_end:%d/%m/%Y} · fechamento {closing_date:%d/%m/%Y}"
        )
        self.stdout.write("")

        parsed = parse_statement_text(text, year, month, card.closing_day)
        if not parsed:
            self.stdout.write(self.style.WARNING("Nenhum item encontrado."))
            return

        header = (
            "prefix | flag | purchase_date | parcel | stmt | ledger_date | amount | note | description"
        )
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        total = 0
        installments = 0
        for item in parsed:
            parcel = (
                f"{item.installments_current}/{item.installments_total}"
                if item.installments_total > 1
                else "-"
            )
            total += item.amount
            if item.installments_total > 1:
                installments += 1
            self.stdout.write(
                f"{item.prefix_raw or '-'} | {item.flag} | {item.purchase_date:%d/%m/%Y} | "
                f"{parcel} | {item.statement_month}/{item.statement_year} | "
                f"{item.ledger_date:%d/%m/%Y} | {item.amount} | {item.inference_note} | {item.description}"
            )

        self.stdout.write("")
        self.stdout.write(f"Itens: {len(parsed)} · Total: {total} · Parcelados: {installments}")

        if options["ai"]:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key or OpenAI is None:
                self.stdout.write(self.style.WARNING("OPENAI_API_KEY ausente ou OpenAI indisponível."))
                return
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            payload = [
                {
                    "purchase_date": item.purchase_date.isoformat(),
                    "statement": f"{item.statement_month}/{item.statement_year}",
                    "parcel": (
                        f"{item.installments_current}/{item.installments_total}"
                        if item.installments_total > 1
                        else None
                    ),
                    "amount": str(item.amount),
                    "note": item.inference_note,
                }
                for item in parsed
            ]
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Analise os itens parseados e indique inconsistências nas inferências de ano ou parcelas.\n"
                            f"Contexto: statement {month}/{year}.\nItens:\n{json.dumps(payload, ensure_ascii=False)}"
                        ),
                    }
                ],
                temperature=0,
            )
            self.stdout.write("\nAI feedback:")
            self.stdout.write(response.choices[0].message.content)
