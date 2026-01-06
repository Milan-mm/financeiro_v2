from django.contrib import admin

from .models import Card, CardPurchase, Category, RecurringExpense


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
