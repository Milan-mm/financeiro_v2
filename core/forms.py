from django import forms
from django.contrib.auth.models import User

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

class UserRegisterForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'usuario@exemplo.com'}),
        label="E-mail",
        required=True
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
        label="Senha",
        required=True
    )

    class Meta:
        model = User
        fields = ['email', 'password']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Este usuário já existe.")
        return email

    def save(self, commit=True):
        # Cria o user mas não salva ainda
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Usa o e-mail como login
        user.set_password(self.cleaned_data['password']) # Hash seguro da senha
        if commit:
            user.save()
        return user
