from datetime import date
from decimal import Decimal

from django.test import TestCase

from finance.utils import build_installment_logical_key


class InstallmentLogicalKeyTests(TestCase):
    def test_logical_key_is_stable_with_normalization(self):
        key_a = build_installment_logical_key(
            "Latam   Air ",
            date(2024, 11, 1),
            Decimal("635.7"),
            4,
        )
        key_b = build_installment_logical_key(
            "LATAM AIR",
            date(2024, 11, 1),
            Decimal("635.70"),
            4,
        )
        self.assertEqual(key_a, key_b)
