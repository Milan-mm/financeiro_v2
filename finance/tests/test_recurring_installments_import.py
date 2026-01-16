from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership
from finance.models import Card, CardPurchaseGroup, ImportBatch, ImportItem, LedgerEntry, RecurringRule
from finance.services import generate_installments_for_group, generate_recurring_instances, pay_recurring_instance


class RecurringInstallmentImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        self.client.login(username="ana", password="pass1234")

    def test_installment_schedule_amounts(self):
        card = Card.objects.create(household=self.household, name="Visa", created_by=self.user)
        group = CardPurchaseGroup.objects.create(
            household=self.household,
            card=card,
            description="Notebook",
            total_amount=Decimal("100.00"),
            installments_count=3,
            first_due_date=date(2024, 5, 10),
            created_by=self.user,
        )
        installments = generate_installments_for_group(group)
        self.assertEqual(len(installments), 3)
        total = sum(inst.amount for inst in installments)
        self.assertEqual(total, Decimal("100.00"))

    def test_recurring_pay_idempotent(self):
        rule = RecurringRule.objects.create(
            household=self.household,
            description="Internet",
            amount=Decimal("120.00"),
            due_day=5,
            start_date=date(2024, 5, 1),
            active=True,
            created_by=self.user,
        )
        instances = generate_recurring_instances(rule, 1)
        instance = instances[0]
        pay_recurring_instance(instance)
        pay_recurring_instance(instance)
        self.assertEqual(LedgerEntry.objects.filter(household=self.household).count(), 1)

    def test_import_confirm_idempotent(self):
        card = Card.objects.create(household=self.household, name="Visa", created_by=self.user)
        batch = ImportBatch.objects.create(
            household=self.household,
            created_by=self.user,
            source_text="teste",
            card=card,
            statement_year=2024,
            statement_month=5,
        )
        ImportItem.objects.create(
            batch=batch,
            purchase_date=date(2024, 5, 20),
            statement_year=2024,
            statement_month=5,
            description="Mercado",
            amount=Decimal("50.00"),
            installments_total=1,
        )
        confirm_url = reverse("finance:import-confirm", args=[batch.id])
        response = self.client.post(confirm_url, {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-MIN_NUM_FORMS": 0,
            "form-MAX_NUM_FORMS": 1000,
            "form-0-id": batch.items.first().id,
            "form-0-purchase_date": "2024-05-20",
            "form-0-description": "Mercado",
            "form-0-amount": "50.00",
            "form-0-installments_total": 1,
            "form-0-installments_current": "",
            "form-0-category": "",
            "form-0-removed": "",
            "card": str(card.id),
            "statement_year": "2024",
            "statement_month": "5",
        })
        self.assertEqual(response.status_code, 302)
        self.client.post(confirm_url, {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-MIN_NUM_FORMS": 0,
            "form-MAX_NUM_FORMS": 1000,
            "form-0-id": batch.items.first().id,
            "form-0-purchase_date": "2024-05-20",
            "form-0-description": "Mercado",
            "form-0-amount": "50.00",
            "form-0-installments_total": 1,
            "form-0-installments_current": "",
            "form-0-category": "",
            "form-0-removed": "",
            "card": str(card.id),
            "statement_year": "2024",
            "statement_month": "5",
        })
        self.assertEqual(LedgerEntry.objects.filter(household=self.household).count(), 1)
