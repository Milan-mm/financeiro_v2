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
    list_select_related = ("household", "category", "account")


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    list_display = ("expected_date", "description", "status", "amount", "household", "category")
    list_filter = ("household", "status")
    search_fields = ("description",)
    date_hierarchy = "expected_date"
    list_select_related = ("household", "category")


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("name", "household", "closing_day", "due_day", "is_active")
    list_filter = ("household", "is_active")
    search_fields = ("name",)


@admin.register(CardPurchaseGroup)
class CardPurchaseGroupAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "card",
        "household",
        "total_amount",
        "installments_count",
        "first_due_date",
        "statement_year",
        "statement_month",
    )
    list_filter = ("card__household", "card")
    search_fields = ("description",)
    list_select_related = ("card", "household")


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = (
        "group",
        "number",
        "due_date",
        "amount",
        "statement_year",
        "statement_month",
        "household",
    )
    list_filter = ("due_date", "statement_year", "statement_month", "group__card__household")
    list_select_related = ("group__card", "group__household")
    autocomplete_fields = ("group",)

    def household(self, obj):
        return obj.group.household

    household.short_description = "Household"


@admin.register(RecurringRule)
class RecurringRuleAdmin(admin.ModelAdmin):
    list_display = ("description", "amount", "due_day", "active", "household")
    list_filter = ("active", "household")
    search_fields = ("description",)


@admin.register(RecurringInstance)
class RecurringInstanceAdmin(admin.ModelAdmin):
    list_display = ("rule", "year", "month", "due_date", "amount", "is_paid")
    list_filter = ("is_paid", "year", "month", "rule__household")
    list_select_related = ("rule",)
    autocomplete_fields = ("rule",)


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "card", "statement_year", "statement_month", "created_at", "household")
    list_filter = ("status", "household")
    search_fields = ("id", "card__name")
    list_select_related = ("card", "household")


@admin.register(ImportItem)
class ImportItemAdmin(admin.ModelAdmin):
    list_display = (
        "batch",
        "purchase_date",
        "description",
        "amount",
        "installments_total",
        "installments_current",
        "purchase_flag",
        "removed",
    )
    list_filter = ("removed",)
    list_select_related = ("batch",)
    autocomplete_fields = ("batch",)


@admin.register(InvestmentAccount)
class InvestmentAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "institution", "household", "active")
    list_filter = ("household", "active")
    search_fields = ("name", "institution")


@admin.register(InvestmentSnapshot)
class InvestmentSnapshotAdmin(admin.ModelAdmin):
    list_display = ("account", "year", "month", "balance", "household")
    list_filter = ("year", "month", "household", "account")
    list_select_related = ("account", "household")
    autocomplete_fields = ("account",)
