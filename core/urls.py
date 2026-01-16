from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("household/missing/", views.household_missing_view, name="household-missing"),
    path("household/missing/", views.household_missing_view, name="household-missing"),
    path("cartoes/", views.cards_view, name="cards"),
    path("lancar-contas/", views.expenses_view, name="expenses"),
    path("configuracoes/", views.settings_view, name="settings"),
    path("logs/", views.system_logs_view, name="system-logs"),
    path("api/month-data/", views.month_data_api, name="month-data"),
    path("api/log-error/", views.log_error_api, name="log-error"),
    path("api/system-logs/", views.system_logs_api, name="system-logs-api"),
    path("api/system-logs/<int:log_id>/", views.system_log_detail_api, name="system-log-detail-api"),
    path("api/logs/pending-count/", views.system_logs_pending_count_api, name="system-logs-pending-count"),
    path("api/recurring/<int:pk>/pay/", views.pay_recurring_api, name="pay-recurring"),
    path("api/recurring/<int:pk>/update-value/", views.update_recurring_value_api, name="update-recurring-value"),
    path("api/card-purchase/", views.card_purchase_create_api, name="card-purchase-create"),
    path("api/card-purchase/<int:purchase_id>/", views.card_purchase_detail_api, name="card-purchase-detail"),
    path("api/recurring-expense/", views.recurring_expense_create_api, name="recurring-expense-create"),
    path(
        "api/recurring-expense/<int:expense_id>/",
        views.recurring_expense_detail_api,
        name="recurring-expense-detail",
    ),
    path("api/import/parse/", views.parse_invoice_api, name="import-parse"),
    path("api/import/save/", views.batch_create_purchases_api, name="import-save"),
    path(
        "api/recurring-payment-toggle/",
        views.recurring_payment_toggle_api,
        name="recurring-payment-toggle",
    ),
path('webhooks/twilio/', views.twilio_webhook, name='twilio_webhook'),
    path("api/categories/", views.categories_api, name="categories-api"), # <--- ESTA LINHA É OBRIGATÓRIA
]
