from django.contrib.auth import get_user_model
from django.db import models

from core.models import Household

User = get_user_model()


class Category(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=20, default="#64748b")
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_categories_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordering", "name"]
        constraints = [
            models.UniqueConstraint(fields=["household", "name"], name="unique_category_household")
        ]

    def __str__(self):
        return self.name


class Account(models.Model):
    class AccountType(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank"
        OTHER = "OTHER", "Other"

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=120)
    institution = models.CharField(max_length=120, blank=True)
    type = models.CharField(max_length=12, choices=AccountType.choices, default=AccountType.BANK)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_accounts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["household", "name"], name="unique_account_household")
        ]

    def __str__(self):
        return self.name


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="ledger_entries")
    date = models.DateField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_entries_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["household", "date"], name="ledger_household_date_idx"),
            models.Index(fields=["household", "kind"], name="ledger_household_kind_idx"),
            models.Index(fields=["household", "category"], name="ledger_household_category_idx"),
        ]

    def __str__(self):
        return f"{self.date} - {self.description}"


class Receivable(models.Model):
    class Status(models.TextChoices):
        EXPECTED = "EXPECTED", "Expected"
        RECEIVED = "RECEIVED", "Received"
        CANCELED = "CANCELED", "Canceled"

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="receivables")
    expected_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EXPECTED)
    received_at = models.DateTimeField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivables",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivables",
    )
    ledger_entry = models.OneToOneField(
        LedgerEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivable",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_receivables_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expected_date", "-id"]
        indexes = [
            models.Index(fields=["household", "expected_date"], name="recv_household_date_idx"),
            models.Index(fields=["household", "status"], name="recv_household_status_idx"),
            models.Index(fields=["household", "category"], name="recv_household_category_idx"),
        ]

    def __str__(self):
        return f"{self.description} ({self.status})"
