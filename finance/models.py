from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
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


class Card(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="cards")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    closing_day = models.PositiveIntegerField(
        default=25, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    due_day = models.PositiveIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_cards_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["household", "name"], name="unique_card_household")
        ]

    def __str__(self):
        return self.name


class CardPurchaseGroup(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="purchase_groups")
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="purchase_groups")
    description = models.CharField(max_length=255)
    logical_key = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    installments_count = models.PositiveIntegerField(default=1)
    first_due_date = models.DateField()
    purchase_date = models.DateField(null=True, blank=True)
    statement_year = models.PositiveIntegerField(null=True, blank=True)
    statement_month = models.PositiveIntegerField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_groups",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_purchase_groups_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-first_due_date", "-id"]

    def __str__(self):
        return self.description


class Installment(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="installments")
    group = models.ForeignKey(CardPurchaseGroup, on_delete=models.CASCADE, related_name="installments")
    number = models.PositiveIntegerField()
    due_date = models.DateField()
    statement_year = models.PositiveIntegerField(null=True, blank=True)
    statement_month = models.PositiveIntegerField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    ledger_entry = models.ForeignKey(
        LedgerEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="installments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "number"]
        constraints = [
            models.UniqueConstraint(fields=["group", "number"], name="unique_installment_group_number")
        ]

    def __str__(self):
        return f"{self.group} {self.number}/{self.group.installments_count}"


class RecurringRule(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="recurring_rules")
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_day = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_rules",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_rules",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_recurring_rules_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["description"]

    def __str__(self):
        return self.description


class RecurringInstance(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="recurring_instances")
    rule = models.ForeignKey(RecurringRule, on_delete=models.CASCADE, related_name="instances")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    ledger_entry = models.ForeignKey(
        LedgerEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_instances",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["year", "month", "due_date"]
        constraints = [
            models.UniqueConstraint(fields=["rule", "year", "month"], name="unique_recurring_rule_month")
        ]

    def __str__(self):
        return f"{self.rule} {self.month}/{self.year}"


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELED = "CANCELED", "Canceled"

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="import_batches")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_import_batches_created",
    )
    card = models.ForeignKey(
        Card,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_batches",
    )
    statement_year = models.PositiveIntegerField(null=True, blank=True)
    statement_month = models.PositiveIntegerField(null=True, blank=True)
    source_text = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch {self.id} ({self.status})"


class ImportItem(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="items")
    purchase_date = models.DateField()
    statement_year = models.PositiveIntegerField()
    statement_month = models.PositiveIntegerField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    installments_total = models.PositiveIntegerField(default=1)
    installments_current = models.PositiveIntegerField(null=True, blank=True)
    purchase_flag = models.CharField(max_length=20, default="UNKNOWN")
    purchase_prefix_raw = models.CharField(max_length=20, blank=True)
    purchase_type_raw = models.CharField(max_length=120, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_items",
    )
    removed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.description


class InvestmentAccount(models.Model):
    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="investment_accounts"
    )
    name = models.CharField(max_length=120)
    institution = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_investment_accounts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["household", "name"], name="unique_investment_account_household"
            )
        ]

    def __str__(self):
        return self.name


class InvestmentSnapshot(models.Model):
    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="investment_snapshots"
    )
    account = models.ForeignKey(
        InvestmentAccount, on_delete=models.CASCADE, related_name="snapshots"
    )
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    balance = models.DecimalField(max_digits=14, decimal_places=2)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_investment_snapshots_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "year", "month"], name="unique_investment_snapshot_account_month"
            )
        ]
        indexes = [
            models.Index(fields=["household", "year", "month"], name="investment_household_ym_idx"),
            models.Index(fields=["account", "year", "month"], name="investment_account_ym_idx"),
        ]

    def __str__(self):
        return f"{self.account} {self.month}/{self.year}"
