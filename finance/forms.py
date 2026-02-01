from django import forms

from django.forms import modelformset_factory

from .models import (
    Account,
    Card,
    CardPurchaseGroup,
    Category,
    ImportItem,
    InvestmentAccount,
    InvestmentSnapshot,
    LedgerEntry,
    Receivable,
    RecurringInstance,
    RecurringRule,
)


class HouseholdScopedForm(forms.ModelForm):
    household = None

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.household = household

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.filter(
                household=household, is_active=True
            )
        if "account" in self.fields:
            self.fields["account"].queryset = Account.objects.filter(
                household=household, is_active=True
            )

    def _validate_household_fk(self, field_name, model_cls):
        value = self.cleaned_data.get(field_name)
        if value and value.household_id != self.household.id:
            raise forms.ValidationError("Seleção inválida para este household.")
        return value


class CategoryForm(HouseholdScopedForm):
    class Meta:
        model = Category
        fields = ["name", "color", "is_active", "ordering"]
        labels = {
            "name": "Nome",
            "color": "Cor",
            "is_active": "Ativa",
            "ordering": "Ordem",
        }


class AccountForm(HouseholdScopedForm):
    class Meta:
        model = Account
        fields = ["name", "institution", "type", "is_active"]
        labels = {
            "name": "Nome",
            "institution": "Instituição",
            "type": "Tipo",
            "is_active": "Ativa",
        }


class LedgerEntryForm(HouseholdScopedForm):
    class Meta:
        model = LedgerEntry
        fields = ["date", "kind", "amount", "description", "category", "account"]
        labels = {
            "date": "Data",
            "kind": "Tipo",
            "amount": "Valor",
            "description": "Descrição",
            "category": "Categoria",
            "account": "Conta",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_category(self):
        return self._validate_household_fk("category", Category)

    def clean_account(self):
        return self._validate_household_fk("account", Account)

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return amount


class ReceivableForm(HouseholdScopedForm):
    class Meta:
        model = Receivable
        fields = [
            "expected_date",
            "amount",
            "description",
            "status",
            "category",
            "account",
        ]
        labels = {
            "expected_date": "Data esperada",
            "amount": "Valor",
            "description": "Descrição",
            "status": "Status",
            "category": "Categoria",
            "account": "Conta",
        }
        widgets = {
            "expected_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_category(self):
        return self._validate_household_fk("category", Category)

    def clean_account(self):
        return self._validate_household_fk("account", Account)

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return amount


class CardForm(HouseholdScopedForm):
    class Meta:
        model = Card
        fields = ["name", "closing_day", "due_day", "is_active"]
        labels = {
            "name": "Nome",
            "closing_day": "Dia de fechamento",
            "due_day": "Dia de vencimento",
            "is_active": "Ativo",
        }


class CardPurchaseGroupForm(HouseholdScopedForm):
    class Meta:
        model = CardPurchaseGroup
        fields = [
            "card",
            "description",
            "total_amount",
            "installments_count",
            "first_due_date",
            "category",
        ]
        labels = {
            "card": "Cartão",
            "description": "Descrição",
            "total_amount": "Valor total",
            "installments_count": "Parcelas",
            "first_due_date": "Primeiro vencimento",
            "category": "Categoria",
        }
        widgets = {
            "first_due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, household=household, **kwargs)
        self.fields["card"].queryset = Card.objects.filter(household=household, is_active=True)

    def clean_total_amount(self):
        amount = self.cleaned_data.get("total_amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return amount


class RecurringRuleForm(HouseholdScopedForm):
    class Meta:
        model = RecurringRule
        fields = [
            "description",
            "amount",
            "due_day",
            "start_date",
            "end_date",
            "active",
            "category",
            "account",
        ]
        labels = {
            "description": "Descrição",
            "amount": "Valor",
            "due_day": "Dia de vencimento",
            "start_date": "Início",
            "end_date": "Fim",
            "active": "Ativo",
            "category": "Categoria",
            "account": "Conta",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return amount


class RecurringInstanceValueOverrideForm(HouseholdScopedForm):
    class Meta:
        model = RecurringInstance
        fields = ["amount"]
        labels = {"amount": "Valor"}

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return amount


class ImportPasteForm(forms.Form):
    card = forms.ModelChoiceField(queryset=Card.objects.none(), required=False, label="Cartão")
    statement_year = forms.IntegerField(min_value=2000, max_value=2100, label="Ano da fatura")
    statement_month = forms.IntegerField(min_value=1, max_value=12, label="Mês da fatura")
    source_text = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}), label="Texto da fatura")

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["card"].queryset = Card.objects.filter(household=household, is_active=True)
        self.fields["card"].widget.attrs.setdefault("class", "form-select")
        self.fields["statement_year"].widget.attrs.setdefault("class", "form-control")
        self.fields["statement_month"].widget.attrs.setdefault("class", "form-control")
        self.fields["source_text"].widget.attrs.setdefault("class", "form-control")


class ImportItemForm(forms.ModelForm):
    class Meta:
        model = ImportItem
        fields = [
            "purchase_date",
            "description",
            "amount",
            "installments_total",
            "installments_current",
            "category",
            "removed",
        ]
        widgets = {
            "purchase_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
        }

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["purchase_date"].input_formats = ["%Y-%m-%d"]

        if household is not None:
            categories = Category.objects.filter(
                household=household,
                is_active=True,
            )
            self.fields["category"].queryset = categories
            if not self.instance.category_id:
                default_category = categories.filter(
                    name__iexact="Despesas pessoais"
                ).first()
                if default_category:
                    self.fields["category"].initial = default_category.id


class InvestmentAccountForm(HouseholdScopedForm):
    class Meta:
        model = InvestmentAccount
        fields = ["name", "institution", "active"]
        labels = {
            "name": "Nome",
            "institution": "Instituição",
            "active": "Ativa",
        }


class InvestmentSnapshotForm(HouseholdScopedForm):
    class Meta:
        model = InvestmentSnapshot
        fields = ["account", "year", "month", "balance"]
        labels = {
            "account": "Conta",
            "year": "Ano",
            "month": "Mês",
            "balance": "Saldo",
        }

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, household=household, **kwargs)
        if household is not None:
            self.fields["account"].queryset = InvestmentAccount.objects.filter(
                household=household, active=True
            )

    def clean_month(self):
        month = self.cleaned_data.get("month")
        if month is not None and (month < 1 or month > 12):
            raise forms.ValidationError("Informe um mês válido.")
        return month

    def clean_balance(self):
        balance = self.cleaned_data.get("balance")
        if balance is not None and balance < 0:
            raise forms.ValidationError("Saldo não pode ser negativo.")
        return balance


ImportReviewFormSet = modelformset_factory(
    ImportItem,
    form=ImportItemForm,
    extra=0,
    can_delete=False,
)
