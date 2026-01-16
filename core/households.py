from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View

from .models import HouseholdMembership


def get_current_household(request):
    if not request.user.is_authenticated:
        return None

    membership = (
        HouseholdMembership.objects.select_related("household")
        .filter(user=request.user, is_primary=True)
        .first()
    )
    if membership:
        return membership.household

    fallback = (
        HouseholdMembership.objects.select_related("household")
        .filter(user=request.user)
        .first()
    )
    return fallback.household if fallback else None


class HouseholdRequiredMixin(View):
    @cached_property
    def household(self):
        return get_current_household(self.request)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self.household:
            return redirect(reverse("household-missing"))
        return super().dispatch(request, *args, **kwargs)
