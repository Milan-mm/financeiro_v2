from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Household(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class HouseholdMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    household = models.ForeignKey(Household, on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "household"], name="unique_household_membership")
        ]

    def __str__(self):
        return f"{self.user} -> {self.household}"

class SystemLog(models.Model):
    LEVEL_ERROR = "ERRO"
    LEVEL_WARNING = "AVISO"
    LEVEL_INFO = "INFO"
    SOURCE_BACKEND = "BACKEND"
    SOURCE_FRONTEND = "FRONTEND"

    LEVEL_CHOICES = [
        (LEVEL_ERROR, "Erro"),
        (LEVEL_WARNING, "Aviso"),
        (LEVEL_INFO, "Info"),
    ]

    SOURCE_CHOICES = [
        (SOURCE_BACKEND, "Backend"),
        (SOURCE_FRONTEND, "Frontend"),
    ]

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_ERROR)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    message = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_level_display()} - {self.message}"


# core/models.py

class QuickExpense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    data = models.DateField(auto_now_add=True)
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    categoria_texto = models.CharField(max_length=100, null=True, blank=True)

    # Campo para saber se isso já foi oficializado/lançado na fatura depois
    processado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.data} - {self.descricao} - R$ {self.valor}"


class CardStatementInitialBalance(models.Model):
    """
    Armazena o saldo inicial (da fatura de cartão anterior) para cada mês/usuário.
    Usado para rastrear o saldo total da fatura ao longo do mês.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    saldo_inicial = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "year", "month"], name="unique_card_statement_balance")
        ]
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.user} - {self.year}-{self.month:02d}: R$ {self.saldo_inicial}"
