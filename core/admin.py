from django.contrib import admin

from .models import (
    Card,
    CardPurchase,
    Category,
    Household,
    HouseholdMembership,
    RecurringExpense,
)


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "user")
    list_filter = ("ativo", "user")


@admin.register(CardPurchase)
class CardPurchaseAdmin(admin.ModelAdmin):
    list_display = ("descricao", "cartao", "valor_total", "parcelas", "primeiro_vencimento", "user")
    list_filter = ("cartao", "user")


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "dia_vencimento", "inicio", "fim", "ativo", "user")
    list_filter = ("ativo", "user")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("nome", "cor", "user")
    list_filter = ("user",)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(HouseholdMembership)
class HouseholdMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "household", "is_primary", "joined_at")
    list_filter = ("is_primary", "household")
    search_fields = ("user__username", "household__name")
