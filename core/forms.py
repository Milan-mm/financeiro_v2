from django import forms

from .models import Card, CardPurchase, RecurringExpense


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["nome", "ativo"]


class CardPurchaseForm(forms.ModelForm):
    class Meta:
        model = CardPurchase
        fields = ["cartao", "descricao", "valor_total", "parcelas", "primeiro_vencimento"]
        widgets = {
            "primeiro_vencimento": forms.DateInput(attrs={"type": "date"}),
        }


class RecurringExpenseForm(forms.ModelForm):
    class Meta:
        model = RecurringExpense
        fields = ["descricao", "valor", "dia_vencimento", "inicio", "fim", "ativo"]
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fim": forms.DateInput(attrs={"type": "date"}),
        }
