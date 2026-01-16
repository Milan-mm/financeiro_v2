from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_quickexpense"),
    ]

    operations = [
        migrations.CreateModel(
            name="Household",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="HouseholdMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_primary", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("household", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.household")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="auth.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="householdmembership",
            constraint=models.UniqueConstraint(fields=("user", "household"), name="unique_household_membership"),
        ),
    ]
