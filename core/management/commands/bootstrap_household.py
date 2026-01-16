import secrets
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import Household, HouseholdMembership


class Command(BaseCommand):
    help = "Cria household e vincula usuários informados"

    def add_arguments(self, parser):
        parser.add_argument("--household-name", required=True)
        parser.add_argument("--users", required=True, help="Lista separada por vírgulas")

    def handle(self, *args, **options):
        household_name = options["household_name"].strip()
        user_list = [u.strip() for u in options["users"].split(",") if u.strip()]
        if not user_list:
            self.stderr.write("Nenhum usuário informado.")
            return

        slug = slugify(household_name)
        household, created = Household.objects.get_or_create(
            slug=slug,
            defaults={"name": household_name},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Household criado: {household.name}"))
        else:
            self.stdout.write(f"Household existente: {household.name}")

        User = get_user_model()
        for username in user_list:
            user, was_created = User.objects.get_or_create(username=username)
            if was_created:
                password = secrets.token_urlsafe(10)
                user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.WARNING(
                        f"Usuário criado: {username} | senha temporária: {password}"
                    )
                )
            else:
                self.stdout.write(f"Usuário existente: {username}")

            membership, membership_created = HouseholdMembership.objects.get_or_create(
                user=user,
                household=household,
            )

            if membership_created:
                if not HouseholdMembership.objects.filter(user=user, is_primary=True).exists():
                    membership.is_primary = True
                    membership.save(update_fields=["is_primary"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Vínculo criado: {username} -> {household.name}"
                    )
                )
            else:
                self.stdout.write(f"Vínculo já existe: {username} -> {household.name}")
