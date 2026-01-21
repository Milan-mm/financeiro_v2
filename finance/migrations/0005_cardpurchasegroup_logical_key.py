from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0004_rename_installments_count_importitem_installments_total_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cardpurchasegroup",
            name="logical_key",
            field=models.CharField(blank=True, db_index=True, max_length=128, null=True),
        ),
    ]
