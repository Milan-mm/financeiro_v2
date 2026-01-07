from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_cardpurchase_tipo_pagamento_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "level",
                    models.CharField(
                        choices=[("ERRO", "Erro"), ("AVISO", "Aviso"), ("INFO", "Info")],
                        default="ERRO",
                        max_length=10,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("BACKEND", "Backend"), ("FRONTEND", "Frontend")],
                        max_length=10,
                    ),
                ),
                ("message", models.CharField(max_length=255)),
                ("details", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_resolved", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
