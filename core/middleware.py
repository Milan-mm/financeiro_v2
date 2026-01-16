import traceback

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .households import get_current_household

from .models import SystemLog


class SystemLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            if not request.path.startswith("/api/log-error/"):
                self._log_exception(exc)
            raise

    def _log_exception(self, exc):
        try:
            message = str(exc) or "Erro interno no servidor"
            SystemLog.objects.create(
                level=SystemLog.LEVEL_ERROR,
                source=SystemLog.SOURCE_BACKEND,
                message=message[:255],
                details=traceback.format_exc(),
            )
        except Exception:
            pass


class HouseholdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = {
            reverse("login"),
            reverse("logout"),
            reverse("household-missing"),
        }

    def __call__(self, request):
        request.household = None
        if request.user.is_authenticated:
            if self._is_exempt(request.path):
                return self.get_response(request)

            request.household = get_current_household(request)
            if request.household is None:
                return redirect("household-missing")

        return self.get_response(request)

    def _is_exempt(self, path):
        if path in self.exempt_paths:
            return True
        if path.startswith("/admin/"):
            return True
        if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
            return True
        if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
            return True
        return False
