from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Card(models.Model):
    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.nome


class CardPurchase(models.Model):
    # Opções de pagamento
    TIPO_CHOICES = [
        ('CREDITO', 'Crédito'),
        ('DEBITO', 'Débito'),
        ('PIX', 'Pix'),
        ('DINHEIRO', 'Dinheiro'),
    ]

    # Cartão agora é opcional (null=True, blank=True)
    cartao = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="compras", null=True, blank=True)

    # Novo campo para saber o tipo
    tipo_pagamento = models.CharField(max_length=10, choices=TIPO_CHOICES, default='CREDITO')

    descricao = models.CharField(max_length=200)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    parcelas = models.PositiveIntegerField(default=1)
    primeiro_vencimento = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Categoria já existia, mas vamos garantir que está acessível
    categoria = models.ForeignKey("Category", on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def valor_parcela(self):
        if self.parcelas <= 0:
            return self.valor_total
        return self.valor_total / self.parcelas

    def __str__(self):
        origem = self.cartao.nome if self.cartao else self.tipo_pagamento
        return f"{self.descricao} ({origem})"


class RecurringExpense(models.Model):
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    dia_vencimento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    inicio = models.DateField()
    fim = models.DateField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    categoria = models.ForeignKey("Category", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.descricao


class RecurringPayment(models.Model):
    expense = models.ForeignKey(RecurringExpense, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["expense", "year", "month"], name="unique_recurring_payment")
        ]

    def __str__(self):
        return f"{self.expense} - {self.month}/{self.year}"


class Category(models.Model):
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=7)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.nome


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