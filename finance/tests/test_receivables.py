from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership
from finance.models import LedgerEntry, Receivable


class ReceivableReceiveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        self.client.login(username="ana", password="pass1234")

    def test_receivable_receive_is_idempotent(self):
        receivable = Receivable.objects.create(
            household=self.household,
            expected_date=date(2024, 5, 20),
            amount=200,
            description="Reembolso",
            created_by=self.user,
        )

        url = reverse("finance:receivable-receive", args=[receivable.id])
        self.client.post(url)
        self.client.post(url)

        receivable.refresh_from_db()
        self.assertEqual(receivable.status, Receivable.Status.RECEIVED)
        self.assertEqual(LedgerEntry.objects.filter(household=self.household).count(), 1)
        self.assertIsNotNone(receivable.ledger_entry)
