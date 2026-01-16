from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership
from finance.billing import get_statement_window
from finance.models import Card, ImportBatch, ImportItem, Installment
from finance.statement_importer import parse_statement_text


class StatementImporterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        self.card = Card.objects.create(
            household=self.household,
            name="Visa",
            closing_day=25,
            due_day=5,
            created_by=self.user,
        )
        self.client.login(username="ana", password="pass1234")

    def test_year_inference(self):
        text = "3 30/03 Mercado 10,00"
        items = parse_statement_text(text, 2026, 1, self.card.closing_day)
        self.assertEqual(items[0].purchase_date.year, 2025)
        text_aug = "2 19/08 Loja 20,00"
        items = parse_statement_text(text_aug, 2026, 1, self.card.closing_day)
        self.assertEqual(items[0].purchase_date.year, 2025)
        text_same = "10/03 Farmacia 30,00"
        items = parse_statement_text(text_same, 2026, 8, self.card.closing_day)
        self.assertEqual(items[0].purchase_date.year, 2026)

    def test_installment_parsing(self):
        text = "2 10/01 Notebook 09/12 100,00"
        items = parse_statement_text(text, 2026, 1, self.card.closing_day)
        self.assertEqual(items[0].installments_current, 9)
        self.assertEqual(items[0].installments_total, 12)

    def test_statement_month_attribution_and_installment_start(self):
        batch = ImportBatch.objects.create(
            household=self.household,
            created_by=self.user,
            card=self.card,
            statement_year=2026,
            statement_month=1,
            source_text="teste",
        )
        ImportItem.objects.create(
            batch=batch,
            purchase_date=date(2025, 12, 20),
            statement_year=2026,
            statement_month=1,
            description="Notebook",
            amount=Decimal("1200.00"),
            installments_total=12,
            installments_current=9,
        )
        response = self.client.post(
            reverse("finance:import-confirm", args=[batch.id]),
            {
                "form-TOTAL_FORMS": 1,
                "form-INITIAL_FORMS": 1,
                "form-MIN_NUM_FORMS": 0,
                "form-MAX_NUM_FORMS": 1000,
                "form-0-id": batch.items.first().id,
                "form-0-purchase_date": "2025-12-20",
                "form-0-description": "Notebook",
                "form-0-amount": "1200.00",
                "form-0-installments_total": 12,
                "form-0-installments_current": 9,
                "form-0-category": "",
                "form-0-removed": "",
                "card": str(self.card.id),
                "statement_year": "2026",
                "statement_month": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        installments = Installment.objects.filter(group__card=self.card).order_by("number")
        self.assertEqual(installments.count(), 4)
        self.assertEqual([inst.number for inst in installments], [9, 10, 11, 12])
        closing_date, _, _ = get_statement_window(2026, 1, self.card.closing_day)
        self.assertEqual(installments.first().ledger_entry.date, closing_date)
