import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from core.models import Household


class Command(BaseCommand):
    help = "Importa dados financeiros de um JSON exportado (escopo household)."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Arquivo JSON exportado")
        parser.add_argument("--household", required=True, help="Slug do household de destino")

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError("Arquivo não encontrado.")

        household = Household.objects.filter(slug=options["household"]).first()
        if household is None:
            raise CommandError("Household não encontrado.")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        for obj in data:
            fields = obj.get("fields", {})
            if "household" in fields:
                fields["household"] = household.pk

        for deserialized in serializers.deserialize("json", json.dumps(data)):
            deserialized.save()

        self.stdout.write(self.style.SUCCESS("Importação concluída."))
