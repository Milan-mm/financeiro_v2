from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership
from finance.models import Card, CardPurchaseGroup, ImportBatch, ImportItem, Installment, LedgerEntry


class InstallmentImportDedupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        self.client.login(username="ana", password="pass1234")
        self.card = Card.objects.create(household=self.household, name="Visa", created_by=self.user)

    def _create_batch(self, year: int, month: int) -> ImportBatch:
        return ImportBatch.objects.create(
            household=self.household,
            created_by=self.user,
            source_text="teste",
            card=self.card,
            statement_year=year,
            statement_month=month,
        )

    def _create_item(
        self,
        batch: ImportBatch,
        purchase_date: date,
        description: str,
        amount: Decimal,
        installments_current: int,
        installments_total: int,
    ) -> ImportItem:
        return ImportItem.objects.create(
            batch=batch,
            purchase_date=purchase_date,
            statement_year=batch.statement_year,
            statement_month=batch.statement_month,
            description=description,
            amount=amount,
            installments_total=installments_total,
            installments_current=installments_current,
        )

    def _confirm_batch(self, batch: ImportBatch, item: ImportItem, year: int, month: int):
        confirm_url = reverse("finance:import-confirm", args=[batch.id])
        return self.client.post(confirm_url, {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-MIN_NUM_FORMS": 0,
            "form-MAX_NUM_FORMS": 1000,
            "form-0-id": item.id,
            "form-0-purchase_date": item.purchase_date.isoformat(),
            "form-0-description": item.description,
            "form-0-amount": f"{item.amount}",
            "form-0-installments_total": item.installments_total,
            "form-0-installments_current": item.installments_current,
            "form-0-category": "",
            "form-0-removed": "",
            "card": str(self.card.id),
            "statement_year": str(year),
            "statement_month": str(month),
        })

    def test_dedup_installment_groups_across_months(self):
        purchase_date = date(2024, 11, 1)
        description = "LATAM AIR"
        amount = Decimal("635.71")

        batch_one = self._create_batch(2024, 1)
        item_one = self._create_item(batch_one, purchase_date, description, amount, 2, 4)
        response = self._confirm_batch(batch_one, item_one, 2024, 1)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CardPurchaseGroup.objects.count(), 1)
        self.assertEqual(Installment.objects.count(), 1)
        self.assertEqual(Installment.objects.first().number, 2)

        batch_two = self._create_batch(2024, 2)
        item_two = self._create_item(batch_two, purchase_date, description, amount, 3, 4)
        response = self._confirm_batch(batch_two, item_two, 2024, 2)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CardPurchaseGroup.objects.count(), 1)
        self.assertEqual(Installment.objects.count(), 2)
        self.assertTrue(Installment.objects.filter(number=3).exists())

        batch_three = self._create_batch(2024, 2)
        item_three = self._create_item(batch_three, purchase_date, description, amount, 3, 4)
        response = self._confirm_batch(batch_three, item_three, 2024, 2)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CardPurchaseGroup.objects.count(), 1)
        self.assertEqual(Installment.objects.count(), 2)
        self.assertEqual(LedgerEntry.objects.count(), 2)

        batch_four = self._create_batch(2024, 3)
        item_four = self._create_item(batch_four, purchase_date, description, Decimal("700.00"), 1, 4)
        response = self._confirm_batch(batch_four, item_four, 2024, 3)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CardPurchaseGroup.objects.count(), 2)
        self.assertEqual(Installment.objects.count(), 3)
