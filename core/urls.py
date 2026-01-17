from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("household/missing/", views.household_missing_view, name="household-missing"),
    path("configuracoes/", views.settings_view, name="settings"),
    path("logs/", views.system_logs_view, name="system-logs"),
    path("logs/<int:log_id>/resolve/", views.system_log_resolve, name="system-log-resolve"),
    path("logs/<int:log_id>/delete/", views.system_log_delete, name="system-log-delete"),
    path("api/log-error/", views.log_error_api, name="log-error"),
    path("api/system-logs/", views.system_logs_api, name="system-logs-api"),
    path("api/system-logs/<int:log_id>/", views.system_log_detail_api, name="system-log-detail-api"),
    path("api/logs/pending-count/", views.system_logs_pending_count_api, name="system-logs-pending-count"),
path('webhooks/twilio/', views.twilio_webhook, name='twilio_webhook'),
]
