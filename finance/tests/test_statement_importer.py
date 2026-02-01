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
    def test_legacy_installments_with_large_purchase_date_gap(self):
        """
        CRITICAL BUG FIX: Testa a geração correta de parcelas futuras para
        compras muito antigas que aparecem na fatura com parcelas intermediárias.
        
        Cenário:
        - Compra original: 25/09/2025
        - Importação: Janeiro/2026 (fatura)
        - Parcela atual: 4/6
        
        Esperado:
        - Parcela 4 (Jan/26) + Parcela 5 (Fev/26) + Parcela 6 (Mar/26)
        
        Bug: Sistema criava datas erradas quando purchase_date era muito anterior
        ao statement_month, porque usava closing_date da fatura atual como
        first_due_date, em vez de calcular a data de vencimento esperada da
        primeira parcela (outubro/2025).
        """
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
            purchase_date=date(2025, 9, 25),  # Compra antiga
            statement_year=2026,
            statement_month=1,
            description="HOTELCOM72066558930566",
            amount=Decimal("304.62"),
            installments_total=6,
            installments_current=4,  # Parcela intermediária
        )
        response = self.client.post(
            reverse("finance:import-confirm", args=[batch.id]),
            {
                "form-TOTAL_FORMS": 1,
                "form-INITIAL_FORMS": 1,
                "form-MIN_NUM_FORMS": 0,
                "form-MAX_NUM_FORMS": 1000,
                "form-0-id": batch.items.first().id,
                "form-0-purchase_date": "2025-09-25",
                "form-0-description": "HOTELCOM72066558930566",
                "form-0-amount": "304.62",
                "form-0-installments_total": 6,
                "form-0-installments_current": 4,
                "form-0-category": "",
                "form-0-removed": "",
                "card": str(self.card.id),
                "statement_year": "2026",
                "statement_month": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        
        # Deve criar apenas as parcelas 4, 5 e 6
        installments = Installment.objects.filter(group__card=self.card).order_by("number")
        self.assertEqual(installments.count(), 3)
        self.assertEqual([inst.number for inst in installments], [4, 5, 6])
        
        # Valida as datas de vencimento
        # Parcela 1 deveria vencer em outubro/2025 (closing_day=25)
        # Logo: 4 em janeiro, 5 em fevereiro, 6 em março
        inst_4 = installments[0]
        inst_5 = installments[1]
        inst_6 = installments[2]
        
        self.assertEqual(inst_4.statement_year, 2026)
        self.assertEqual(inst_4.statement_month, 1)
        self.assertEqual(inst_4.due_date.day, 25)  # closing_day
        
        self.assertEqual(inst_5.statement_year, 2026)
        self.assertEqual(inst_5.statement_month, 2)
        self.assertEqual(inst_5.due_date.day, 25)
        
        self.assertEqual(inst_6.statement_year, 2026)
        self.assertEqual(inst_6.statement_month, 3)
        self.assertEqual(inst_6.due_date.day, 25)