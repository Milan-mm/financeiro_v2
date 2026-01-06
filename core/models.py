from django.db import models


class Card(models.Model):
    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class CardPurchase(models.Model):
    cartao = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="compras")
    descricao = models.CharField(max_length=200)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    parcelas = models.PositiveIntegerField(default=1)
    primeiro_vencimento = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def valor_parcela(self):
        if self.parcelas <= 0:
            return self.valor_total
        return self.valor_total / self.parcelas

    def __str__(self):
        return f"{self.descricao} ({self.cartao})"


class RecurringExpense(models.Model):
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    dia_vencimento = models.PositiveSmallIntegerField()
    inicio = models.DateField()
    fim = models.DateField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

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
