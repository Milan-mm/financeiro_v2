import traceback

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
