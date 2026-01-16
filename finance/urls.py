from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("categories/", views.category_list, name="categories"),
    path("categories/new/", views.category_create, name="category-create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category-edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category-delete"),
    path("accounts/", views.account_list, name="accounts"),
    path("accounts/new/", views.account_create, name="account-create"),
    path("accounts/<int:pk>/edit/", views.account_edit, name="account-edit"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account-delete"),
    path("entries/", views.entry_list, name="entries"),
    path("entries/new/", views.entry_create, name="entry-create"),
    path("entries/<int:pk>/edit/", views.entry_edit, name="entry-edit"),
    path("entries/<int:pk>/delete/", views.entry_delete, name="entry-delete"),
    path("receivables/", views.receivable_list, name="receivables"),
    path("receivables/new/", views.receivable_create, name="receivable-create"),
    path("receivables/<int:pk>/edit/", views.receivable_edit, name="receivable-edit"),
    path("receivables/<int:pk>/delete/", views.receivable_delete, name="receivable-delete"),
    path("receivables/<int:pk>/receive/", views.receivable_receive, name="receivable-receive"),
    path("receivables/<int:pk>/cancel/", views.receivable_cancel, name="receivable-cancel"),
]
