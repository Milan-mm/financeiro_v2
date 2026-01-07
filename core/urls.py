from django.urls import path

from . import views


urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("cartoes/", views.cards_view, name="cards"),
    path("lancar-contas/", views.expenses_view, name="expenses"),
    path("configuracoes/", views.settings_view, name="settings"),
    path("api/month-data/", views.month_data_api, name="month-data"),
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
    path(
        "api/recurring-payment-toggle/",
        views.recurring_payment_toggle_api,
        name="recurring-payment-toggle",
    ),
    path("api/categories/", views.categories_api, name="categories-api"), # <--- ESTA LINHA É OBRIGATÓRIA
]
