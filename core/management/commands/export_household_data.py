import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from core.models import Household
from finance import models as finance_models


HOUSEHOLD_MODELS = [
    finance_models.Category,
    finance_models.Account,
    finance_models.Card,
    finance_models.CardPurchaseGroup,
    finance_models.Installment,
    finance_models.RecurringRule,
    finance_models.RecurringInstance,
    finance_models.Receivable,
    finance_models.LedgerEntry,
    finance_models.InvestmentAccount,
    finance_models.InvestmentSnapshot,
    finance_models.ImportBatch,
    finance_models.ImportItem,
]


class Command(BaseCommand):
    help = "Exporta dados financeiros de um household para JSON."

    def add_arguments(self, parser):
        parser.add_argument("--household", required=True, help="Slug do household")
        parser.add_argument("--output", required=True, help="Arquivo de saída JSON")

    def handle(self, *args, **options):
        slug = options["household"]
        output_path = Path(options["output"])
        household = Household.objects.filter(slug=slug).first()
        if household is None:
            raise CommandError("Household não encontrado.")

        payload = []
        for model in HOUSEHOLD_MODELS:
            queryset = model.objects.filter(household=household)
            payload.extend(json.loads(serializers.serialize("json", queryset)))

        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Exportado para {output_path}"))
