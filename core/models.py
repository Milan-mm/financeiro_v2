from django.db import models
from django.contrib.auth.models import User


class Lancamento(models.Model):
    TIPO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
    ]

    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    categoria = models.CharField(max_length=50, blank=True)  # Ex: Mercado, Luz

    # Quem lançou (Você ou Esposa)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.descricao} - R$ {self.valor}"