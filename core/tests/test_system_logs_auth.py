from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership, SystemLog


class SystemLogsAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)
        SystemLog.objects.create(
            level=SystemLog.LEVEL_ERROR,
            source=SystemLog.SOURCE_BACKEND,
            message="Erro",
            details="stack",
        )

    def test_primary_user_can_access_logs(self):
        self.client.login(username="ana", password="pass1234")
        response = self.client.get(reverse("system-logs"))
        self.assertEqual(response.status_code, 200)

    def test_non_primary_user_cannot_access_logs(self):
        other_user = get_user_model().objects.create_user(username="bia", password="pass1234")
        HouseholdMembership.objects.create(user=other_user, household=self.household, is_primary=False)
        self.client.login(username="bia", password="pass1234")
        response = self.client.get(reverse("system-logs"))
        self.assertEqual(response.status_code, 403)
