from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import SystemLog


class Command(BaseCommand):
    help = "Remove logs antigos do sistema para evitar crescimento excessivo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Remove logs com mais de X dias (padrão: 30).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = SystemLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} logs antigos removidos."))
