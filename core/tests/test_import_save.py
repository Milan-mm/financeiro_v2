import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Card, CardPurchase, Category


class ImportSaveApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.card = Card.objects.create(nome="Visa", user=self.user)
        self.category = Category.objects.create(nome="Mercado", cor="#000000", user=self.user)
        self.client.force_login(self.user)

    def _post_items(self, items):
        payload = {"card_id": self.card.id, "items": items}
        return self.client.post(
            "/api/import/save/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_import_avista_creates_purchase(self):
        response = self._post_items(
            [
                {
                    "data": "2024-01-10",
                    "descricao": "Compra a vista",
                    "valor": "100",
                    "parcelas": 1,
                    "category_id": self.category.id,
                }
            ]
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["handler"], "batch_create_purchases_api_v2")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total_now"], 1)

        purchase = CardPurchase.objects.get()
        self.assertEqual(purchase.valor_total, Decimal("100.00"))
        self.assertEqual(purchase.parcelas, 1)

    def test_import_parcelado_uses_parcela_value(self):
        response = self._post_items(
            [
                {
                    "data": "2024-02-10",
                    "descricao": "Compra parcelada",
                    "valor": "33.33",
                    "parcelas": 3,
                }
            ]
        )

        self.assertEqual(response.status_code, 200)
        purchase = CardPurchase.objects.get()
        self.assertEqual(purchase.valor_total, Decimal("99.99"))
        self.assertEqual(purchase.parcelas, 3)

    def test_import_parcelado_with_total_informado(self):
        response = self._post_items(
            [
                {
                    "data": "2024-03-10",
                    "descricao": "Compra total informado",
                    "valor": "33.33",
                    "parcelas": 3,
                    "valor_total_compra": "100.00",
                }
            ]
        )

        self.assertEqual(response.status_code, 200)
        purchase = CardPurchase.objects.get()
        self.assertEqual(purchase.valor_total, Decimal("100.00"))
        self.assertEqual(purchase.parcelas, 3)
