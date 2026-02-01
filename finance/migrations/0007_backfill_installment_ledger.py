"""Backfill LedgerEntry for Installment rows missing ledger_entry.

This data migration will create a LedgerEntry for each Installment that
doesn't have one and attempt to link to an existing LedgerEntry when a
matching entry exists (same household, date and amount). It is idempotent.
"""
from django.db import migrations, transaction


def create_missing_ledger_entries(apps, schema_editor):
    Installment = apps.get_model("finance", "Installment")
    LedgerEntry = apps.get_model("finance", "LedgerEntry")
    Group = apps.get_model("finance", "CardPurchaseGroup")

    with transaction.atomic():
        missing = Installment.objects.select_related("group", "household").filter(ledger_entry__isnull=True)
        for inst in missing.iterator():
            group = inst.group

            # try to find a matching existing LedgerEntry
            existing = LedgerEntry.objects.filter(
                household=inst.household_id,
                date=inst.due_date,
                amount=inst.amount,
            ).order_by("id")

            entry = None
            if existing.exists():
                # prefer an entry whose description contains the group's description
                entry = existing.filter(description__icontains=(group.description or "")).first() or existing.first()

            if entry is None:
                desc = f"{group.description} {inst.number}/{getattr(group, 'installments_count', None) or ''}".strip()
                entry = LedgerEntry.objects.create(
                    household_id=inst.household_id,
                    date=inst.due_date,
                    kind="EXPENSE",
                    amount=inst.amount,
                    description=desc,
                    category_id=getattr(group, "category_id", None),
                    created_by_id=getattr(group, "created_by_id", None),
                )

            # link and save
            inst.ledger_entry_id = entry.id
            inst.save(update_fields=["ledger_entry"])


def noop_reverse(apps, schema_editor):
    # no-op: do not delete created ledger entries automatically
    return


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0006_backfill_logical_keys"),
    ]

    operations = [
        migrations.RunPython(create_missing_ledger_entries, reverse_code=noop_reverse),
    ]
