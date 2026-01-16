from django.core.management.base import BaseCommand

from finance.models import RecurringRule
from finance.services import generate_recurring_instances


class Command(BaseCommand):
    help = "Gera instâncias de recorrências para os próximos meses (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--months-ahead", type=int, default=6)

    def handle(self, *args, **options):
        months_ahead = options["months_ahead"]
        created_total = 0
        for rule in RecurringRule.objects.filter(active=True):
            created = generate_recurring_instances(rule, months_ahead)
            created_total += len(created)
        self.stdout.write(self.style.SUCCESS(f"Instâncias criadas: {created_total}"))
