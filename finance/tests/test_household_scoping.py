from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Household, HouseholdMembership
from finance.models import Category


class HouseholdScopingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ana", password="pass1234")
        self.household = Household.objects.create(name="Casa", slug="casa")
        HouseholdMembership.objects.create(user=self.user, household=self.household, is_primary=True)

        self.other_household = Household.objects.create(name="Outra", slug="outra")
        other_user = get_user_model().objects.create_user(username="bob", password="pass1234")
        HouseholdMembership.objects.create(user=other_user, household=self.other_household, is_primary=True)

        Category.objects.create(household=self.household, name="Mercado")
        Category.objects.create(household=self.other_household, name="Viagem")

    def test_user_sees_only_own_household_categories(self):
        self.client.login(username="ana", password="pass1234")
        response = self.client.get(reverse("finance:categories"))
        self.assertContains(response, "Mercado")
        self.assertNotContains(response, "Viagem")

    def test_user_without_household_is_redirected(self):
        outsider = get_user_model().objects.create_user(username="solo", password="pass1234")
        self.client.login(username="solo", password="pass1234")
        response = self.client.get(reverse("finance:categories"))
        self.assertRedirects(response, reverse("household-missing"))
