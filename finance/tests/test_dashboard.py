from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Household, HouseholdMembership
from finance.models import LedgerEntry, Receivable


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        self.client.login(username="ana", password="pass1234")

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_totals(self):
        LedgerEntry.objects.create(
            household=self.household,
            date=date(2024, 5, 10),
            kind=LedgerEntry.Kind.INCOME,
            amount=1000,
            description="Salário",
        )
        LedgerEntry.objects.create(
            household=self.household,
            date=date(2024, 5, 12),
            kind=LedgerEntry.Kind.EXPENSE,
            amount=250,
            description="Mercado",
        )
        Receivable.objects.create(
            household=self.household,
            expected_date=date(2024, 5, 20),
            amount=500,
            description="Freela",
            status=Receivable.Status.EXPECTED,
        )
        receivable_received = Receivable.objects.create(
            household=self.household,
            expected_date=date(2024, 5, 5),
            amount=200,
            description="Reembolso",
            status=Receivable.Status.RECEIVED,
        )
        receivable_received.received_at = timezone.make_aware(datetime(2024, 5, 6, 10, 0))
        receivable_received.save(update_fields=["received_at"])

        response = self.client.get(reverse("dashboard"), {"year": 2024, "month": 5})
        self.assertEqual(response.context["total_income"], 1000)
        self.assertEqual(response.context["total_expense"], 250)
        self.assertEqual(response.context["net"], 750)
        self.assertEqual(response.context["expected_total"], 500)
        self.assertEqual(response.context["received_total"], 200)

    def test_dashboard_is_household_scoped(self):
        other_household = Household.objects.create(name="Outra", slug="outra")
        LedgerEntry.objects.create(
            household=other_household,
            date=date(2024, 5, 12),
            kind=LedgerEntry.Kind.INCOME,
            amount=999,
            description="Outro",
        )
        response = self.client.get(reverse("dashboard"), {"year": 2024, "month": 5})
        self.assertEqual(response.context["total_income"], 0)
