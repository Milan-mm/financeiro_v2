from django.contrib import admin

from .models import Card, CardPurchase, RecurringExpense


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    list_filter = ("ativo",)


@admin.register(CardPurchase)
class CardPurchaseAdmin(admin.ModelAdmin):
    list_display = ("descricao", "cartao", "valor_total", "parcelas", "primeiro_vencimento")
    list_filter = ("cartao",)


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "dia_vencimento", "inicio", "fim", "ativo")
    list_filter = ("ativo",)
