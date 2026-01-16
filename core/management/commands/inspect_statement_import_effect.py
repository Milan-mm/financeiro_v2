from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from finance.billing import get_statement_window
from finance.models import Card
from finance.statement_importer import parse_statement_text


class Command(BaseCommand):
    help = "Simula o efeito da importação de fatura sem gravar no banco."

    def add_arguments(self, parser):
        parser.add_argument("--card", type=int, required=True)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)
        parser.add_argument("--file", type=str)
        parser.add_argument("--text", type=str)

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
        closing_date, _, _ = get_statement_window(year, month, card.closing_day)
        self.stdout.write(f"Simulação para {card.name} (statement {month}/{year})")
        self.stdout.write(f"Fechamento: {closing_date:%d/%m/%Y}")
        self.stdout.write("")

        parsed = parse_statement_text(text, year, month, card.closing_day)
        if not parsed:
            self.stdout.write(self.style.WARNING("Nenhum item encontrado."))
            return

        for item in parsed:
            current = item.installments_current or 1
            total = item.installments_total
            self.stdout.write(
                f"- {item.description}: {item.amount} "
                f"({current}/{total if total > 1 else 1})"
            )
            for offset, number in enumerate(range(current, total + 1)):
                target_month = month + offset
                target_year = year + (target_month - 1) // 12
                target_month = ((target_month - 1) % 12) + 1
                closing_date, _, _ = get_statement_window(
                    target_year, target_month, card.closing_day
                )
                self.stdout.write(
                    f"  - Parcela {number}/{total} -> statement {target_month}/{target_year} "
                    f"(ledger_date {closing_date:%d/%m/%Y})"
                )
