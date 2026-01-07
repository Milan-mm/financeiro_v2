from decimal import Decimal

from django.test import SimpleTestCase

from core.installments import calculate_installment_values


class CalculateInstallmentValuesTests(SimpleTestCase):
    def test_avista(self):
        total, parcela, regra = calculate_installment_values(Decimal("100"), 1)
        self.assertEqual(total, Decimal("100.00"))
        self.assertEqual(parcela, Decimal("100.00"))
        self.assertEqual(regra, "avista")

    def test_parcela_informada(self):
        total, parcela, regra = calculate_installment_values(Decimal("33.33"), 3)
        self.assertEqual(parcela, Decimal("33.33"))
        self.assertEqual(total, Decimal("99.99"))
        self.assertEqual(regra, "parcela_informada")

    def test_total_informado(self):
        total, parcela, regra = calculate_installment_values(
            Decimal("33.33"),
            3,
            valor_total_compra=Decimal("100"),
        )
        self.assertEqual(total, Decimal("100.00"))
        self.assertEqual(parcela, Decimal("33.33"))
        self.assertEqual(regra, "total_informado")
