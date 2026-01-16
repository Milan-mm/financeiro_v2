from django.contrib import admin

from .models import Account, Category, LedgerEntry, Receivable


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "household", "is_active", "ordering")
    list_filter = ("household", "is_active")
    search_fields = ("name",)
    ordering = ("ordering", "name")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "institution", "type", "household", "is_active")
    list_filter = ("household", "type", "is_active")
    search_fields = ("name", "institution")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "kind", "amount", "household", "category", "account")
    list_filter = ("household", "kind", "category", "account")
    search_fields = ("description",)
    date_hierarchy = "date"


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    list_display = ("expected_date", "description", "status", "amount", "household", "category")
    list_filter = ("household", "status")
    search_fields = ("description",)
    date_hierarchy = "expected_date"
