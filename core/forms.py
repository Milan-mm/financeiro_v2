from django import forms
from django.contrib.auth.models import User

from .models import Card, CardPurchase, RecurringExpense, Category


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["nome", "ativo"]


class CardPurchaseForm(forms.ModelForm):
    nova_categoria = forms.CharField(required=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Ou digite nova categoria'}))

    class Meta:
        model = CardPurchase
        # Adicionamos tipo_pagamento e categoria aos campos
        fields = ["cartao", "descricao", "valor_total", "parcelas", "primeiro_vencimento", "tipo_pagamento",
                  "categoria"]
        widgets = {
            "primeiro_vencimento": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo_pagamento")
        cartao = cleaned_data.get("cartao")
        parcelas = cleaned_data.get("parcelas") or 1

        # Validação: Crédito exige Cartão
        if tipo == 'CREDITO' and not cartao:
            self.add_error('cartao', 'Para pagamento no crédito, selecione um cartão.')

        # Se não for crédito, removemos cartão e forçamos 1 parcela
        if tipo != 'CREDITO':
            cleaned_data['cartao'] = None
            cleaned_data['parcelas'] = 1

        return cleaned_data

    def save(self, commit=True):
        # Lógica para criar categoria nova on-the-fly
        instance = super().save(commit=False)
        nova_cat_nome = self.cleaned_data.get('nova_categoria')
        if nova_cat_nome:
            # Cria a categoria se o usuário digitou uma nova
            cat, created = Category.objects.get_or_create(
                nome=nova_cat_nome,
                user=instance.user,
                defaults={'cor': '#6c757d'}  # Cor padrão cinza
            )
            instance.categoria = cat

        if commit:
            instance.save()
        return instance


class RecurringExpenseForm(forms.ModelForm):
    # Campo para criar nova categoria "on-the-fly"
    nova_categoria = forms.CharField(required=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Ou digite nova categoria'}))

    class Meta:
        model = RecurringExpense
        # Adicionamos 'categoria' à lista de campos
        fields = ["descricao", "valor", "dia_vencimento", "inicio", "fim", "ativo", "categoria"]
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fim": forms.DateInput(attrs={"type": "date"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Lógica idêntica à de Compras para criar categoria
        nova_cat_nome = self.cleaned_data.get('nova_categoria')
        if nova_cat_nome:
            cat, created = Category.objects.get_or_create(
                nome=nova_cat_nome,
                user=instance.user,
                defaults={'cor': '#6c757d'}
            )
            instance.categoria = cat

        if commit:
            instance.save()
        return instance

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
