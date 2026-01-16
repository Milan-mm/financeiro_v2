from django.contrib import admin

from .models import (
    Account,
    Card,
    CardPurchaseGroup,
    Category,
    ImportBatch,
    ImportItem,
    Installment,
    InvestmentAccount,
    InvestmentSnapshot,
    LedgerEntry,
    Receivable,
    RecurringInstance,
    RecurringRule,
)


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


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("name", "household", "is_active")
    list_filter = ("household", "is_active")
    search_fields = ("name",)


@admin.register(CardPurchaseGroup)
class CardPurchaseGroupAdmin(admin.ModelAdmin):
    list_display = ("description", "card", "total_amount", "installments_count", "first_due_date")
    list_filter = ("card",)
    search_fields = ("description",)


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ("group", "number", "due_date", "amount")
    list_filter = ("due_date",)


@admin.register(RecurringRule)
class RecurringRuleAdmin(admin.ModelAdmin):
    list_display = ("description", "amount", "due_day", "active", "household")
    list_filter = ("active", "household")


@admin.register(RecurringInstance)
class RecurringInstanceAdmin(admin.ModelAdmin):
    list_display = ("rule", "year", "month", "due_date", "amount", "is_paid")
    list_filter = ("is_paid", "year", "month")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_at", "household")
    list_filter = ("status",)


@admin.register(ImportItem)
class ImportItemAdmin(admin.ModelAdmin):
    list_display = ("batch", "date", "description", "amount", "installments_count", "removed")
    list_filter = ("removed",)


@admin.register(InvestmentAccount)
class InvestmentAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "institution", "household", "active")
    list_filter = ("household", "active")
    search_fields = ("name", "institution")


@admin.register(InvestmentSnapshot)
class InvestmentSnapshotAdmin(admin.ModelAdmin):
    list_display = ("account", "year", "month", "balance", "household")
    list_filter = ("year", "month", "household")
