from django import forms

from .models import Account, Category, LedgerEntry, Receivable


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
