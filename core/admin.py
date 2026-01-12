from django.contrib import admin, messages

from .models import Card, CardPurchase, Category, RecurringExpense


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "user")
    list_filter = ("ativo", "user")


@admin.register(CardPurchase)
class CardPurchaseAdmin(admin.ModelAdmin):
    list_display = ("descricao", "cartao", "valor_total", "parcelas", "primeiro_vencimento", "user")
    list_filter = ("cartao", "user")
    actions = ["delete_all_for_selected_cards"]

    @admin.action(description="Excluir todas as transações do cartão selecionado")
    def delete_all_for_selected_cards(self, request, queryset):
        card_ids = list(
            queryset.exclude(cartao_id__isnull=True).values_list("cartao_id", flat=True).distinct()
        )
        if not card_ids:
            self.message_user(request, "Nenhum cartão válido selecionado.", level=messages.WARNING)
            return
        deleted_count, _ = CardPurchase.objects.filter(cartao_id__in=card_ids).delete()
        self.message_user(
            request,
            f"{deleted_count} transações removidas para {len(card_ids)} cartão(ões).",
            level=messages.SUCCESS,
        )


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ("descricao", "valor", "dia_vencimento", "inicio", "fim", "ativo", "user")
    list_filter = ("ativo", "user")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("nome", "cor", "user")
    list_filter = ("user",)
