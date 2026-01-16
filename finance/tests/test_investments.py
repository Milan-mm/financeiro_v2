from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership
from finance.models import InvestmentAccount, InvestmentSnapshot, LedgerEntry
from finance.services_investments import compute_mom_deltas


class InvestmentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        self.client.login(username="ana", password="pass1234")

    def test_snapshot_unique_constraint(self):
        account = InvestmentAccount.objects.create(
            household=self.household, name="XP Invest", created_by=self.user
        )
        InvestmentSnapshot.objects.create(
            household=self.household,
            account=account,
            year=2024,
            month=5,
            balance=Decimal("100.00"),
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            InvestmentSnapshot.objects.create(
                household=self.household,
                account=account,
                year=2024,
                month=5,
                balance=Decimal("120.00"),
                created_by=self.user,
            )

    def test_mom_delta_zero_handling(self):
        deltas = compute_mom_deltas([Decimal("0.00"), Decimal("0.00"), Decimal("10.00")])
        self.assertEqual(deltas[1].delta_pct, Decimal("0.00"))
        self.assertIsNone(deltas[2].delta_pct)

    def test_household_scoping_on_accounts(self):
        other_household = Household.objects.create(name="Outra", slug="outra")
        other_account = InvestmentAccount.objects.create(
            household=other_household, name="Outra conta", created_by=self.user
        )
        url = reverse("finance:investment-account-edit", args=[other_account.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_annual_stats_totals(self):
        LedgerEntry.objects.create(
            household=self.household,
            date=date(2024, 5, 1),
            kind=LedgerEntry.Kind.INCOME,
            amount=Decimal("100.00"),
            description="Salário",
            created_by=self.user,
        )
        LedgerEntry.objects.create(
            household=self.household,
            date=date(2024, 6, 1),
            kind=LedgerEntry.Kind.EXPENSE,
            amount=Decimal("40.00"),
            description="Mercado",
            created_by=self.user,
        )
        response = self.client.get(reverse("finance:annual-stats"), {"year": 2024})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["income_total"], Decimal("100.00"))
        self.assertEqual(response.context["expense_total"], Decimal("40.00"))
