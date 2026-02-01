from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .billing import get_statement_window
from .models import (
    CardPurchaseGroup,
    ImportBatch,
    ImportItem,
    Installment,
    LedgerEntry,
    RecurringInstance,
    RecurringRule,
)


@dataclass
class InstallmentPlan:
    amounts: list[Decimal]
    due_dates: list[date]


def last_day_of_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def add_months(start: date, months: int) -> date:
    total_month = start.month - 1 + months
    year = start.year + total_month // 12
    month = total_month % 12 + 1
    day = min(start.day, last_day_of_month(year, month))
    return date(year, month, day)


def installment_plan(total: Decimal, count: int, first_due: date) -> InstallmentPlan:
    if count <= 0:
        raise ValueError("installments_count must be positive")
    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    base = (total / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    amounts = [base for _ in range(count)]
    remainder = total - sum(amounts)
    idx = 0
    while remainder != Decimal("0.00"):
        amounts[idx] = (amounts[idx] + Decimal("0.01")).quantize(Decimal("0.01"))
        remainder -= Decimal("0.01")
        idx += 1
        if idx >= count:
            idx = 0
    due_dates = [add_months(first_due, i) for i in range(count)]
    return InstallmentPlan(amounts=amounts, due_dates=due_dates)


def generate_installments_for_group(group: CardPurchaseGroup) -> list[Installment]:
    if group.installments.exists():
        return list(group.installments.all())

    plan = installment_plan(group.total_amount, group.installments_count, group.first_due_date)
    created = []

    with transaction.atomic():
        for idx, (amount, due_date) in enumerate(zip(plan.amounts, plan.due_dates), start=1):
            entry = LedgerEntry.objects.create(
                household=group.household,
                date=due_date,
                kind=LedgerEntry.Kind.EXPENSE,
                amount=amount,
                description=f"{group.description} {idx}/{group.installments_count}",
                category=group.category,
                created_by=group.created_by,
            )
            installment = Installment.objects.create(
                household=group.household,
                group=group,
                number=idx,
                due_date=due_date,
                statement_year=due_date.year,
                statement_month=due_date.month,
                amount=amount,
                ledger_entry=entry,
            )
            created.append(installment)
    return created


def generate_installments_from_statement(
    group: CardPurchaseGroup,
    statement_year: int,
    statement_month: int,
    current_installment: int = 1,
) -> list[Installment]:
    plan = installment_plan(group.total_amount, group.installments_count, group.first_due_date)
    created = []
    target_number = max(1, current_installment)
    target_month = statement_month
    target_year = statement_year
    closing_date, _, _ = get_statement_window(target_year, target_month, group.card.closing_day)
    amount = plan.amounts[target_number - 1]
    entry_description = f"{group.description} {target_number}/{group.installments_count}"
    installment, was_created = Installment.objects.get_or_create(
        household=group.household,
        group=group,
        number=target_number,
        defaults={
            "due_date": closing_date,
            "statement_year": target_year,
            "statement_month": target_month,
            "amount": amount,
        },
    )
    if was_created:
        entry = LedgerEntry.objects.create(
            household=group.household,
            date=closing_date,
            kind=LedgerEntry.Kind.EXPENSE,
            amount=amount,
            description=entry_description,
            category=group.category,
            created_by=group.created_by,
        )
        installment.ledger_entry = entry
        installment.save(update_fields=["ledger_entry"])
        created.append(installment)
    return created


def regenerate_future_installments(group: CardPurchaseGroup, from_date: date) -> list[Installment]:
    with transaction.atomic():
        future_installments = group.installments.filter(due_date__gte=from_date)
        ledger_ids = list(future_installments.exclude(ledger_entry=None).values_list("ledger_entry_id", flat=True))
        future_installments.delete()
        if ledger_ids:
            LedgerEntry.objects.filter(id__in=ledger_ids).delete()
    return generate_installments_for_group(group)


def generate_recurring_instances(rule: RecurringRule, months_ahead: int) -> list[RecurringInstance]:
    print("\n[RECURRING_GENERATE]")
    print("rule:", rule.id, "-", rule.description)
    print("months_ahead:", months_ahead)

    if months_ahead <= 0:
        print("ABORT: months_ahead <= 0")
        return []

    today = timezone.localdate()
    start_month = date(today.year, today.month, 1)

    print("today:", today)
    print("start_month:", start_month)
    print("rule.start_date:", rule.start_date)
    print("rule.end_date:", rule.end_date)

    instances = []

    for offset in range(months_ahead):
        target_month = add_months(start_month, offset)
        print(f"\n[CHECK] target:", target_month.year, target_month.month)

        if rule.start_date > target_month:
            print("SKIP: before start_date")
            continue

        if rule.end_date and rule.end_date < target_month:
            print("SKIP: after end_date")
            continue

        due_day = min(
            rule.due_day,
            last_day_of_month(target_month.year, target_month.month),
        )
        due_date = date(target_month.year, target_month.month, due_day)

        instance, created = RecurringInstance.objects.get_or_create(
            household=rule.household,
            rule=rule,
            year=target_month.year,
            month=target_month.month,
            defaults={
                "due_date": due_date,
                "amount": rule.amount,
            },
        )

        print(
            "RESULT:",
            f"{target_month.month}/{target_month.year}",
            "→",
            "CREATED" if created else "EXISTS",
            f"(id={instance.id})",
        )

        if created:
            instances.append(instance)

    print("[RECURRING_GENERATE] created:", len(instances))
    return instances


def generate_future_installments_for_household(
    household_id: int,
    months_ahead: int,
    start_month: date | None = None,
) -> int:
    print("\n[INSTALLMENTS_GENERATE]")
    print("household:", household_id)
    print("months_ahead:", months_ahead)

    if months_ahead <= 0:
        print("ABORT: months_ahead <= 0")
        return 0

    start_month = start_month or date(timezone.localdate().year, timezone.localdate().month, 1)
    end_month = add_months(start_month, months_ahead)

    print("start_month:", start_month)
    print("end_month (exclusive):", end_month)

    groups = CardPurchaseGroup.objects.filter(
        household_id=household_id,
        installments_count__gt=1,
    )
    print("installment groups found:", groups.count())

    created_count = 0
    for group in groups:
        plan = installment_plan(group.total_amount, group.installments_count, group.first_due_date)
        for idx, (amount, due_date) in enumerate(
            zip(plan.amounts, plan.due_dates),
            start=1,
        ):
            if due_date < start_month or due_date >= end_month:
                continue
            installment, created = Installment.objects.get_or_create(
                household=group.household,
                group=group,
                number=idx,
                defaults={
                    "due_date": due_date,
                    "statement_year": due_date.year,
                    "statement_month": due_date.month,
                    "amount": amount,
                },
            )
            if created:
                created_count += 1
                print(
                    "[INSTALLMENTS_GENERATE] created",
                    f"group={group.id}",
                    f"number={idx}",
                    f"due={due_date}",
                    f"installment_id={installment.id}",
                )

    print("[INSTALLMENTS_GENERATE] created:", created_count)
    return created_count


def pay_recurring_instance(instance: RecurringInstance) -> RecurringInstance:
    with transaction.atomic():
        instance = RecurringInstance.objects.select_for_update().get(pk=instance.pk)
        if instance.is_paid:
            return instance
        entry = LedgerEntry.objects.create(
            household=instance.household,
            date=instance.due_date,
            kind=LedgerEntry.Kind.EXPENSE,
            amount=instance.amount,
            description=instance.rule.description,
            category=instance.rule.category,
            account=instance.rule.account,
            created_by=instance.rule.created_by,
        )
        instance.is_paid = True
        instance.paid_at = timezone.now()
        instance.ledger_entry = entry
        instance.save(update_fields=["is_paid", "paid_at", "ledger_entry"])
    return instance


def build_import_items(batch: ImportBatch, raw_items: list[dict]) -> list[ImportItem]:
    created_items = []
    for item in raw_items:
        created_items.append(
            ImportItem.objects.create(
                batch=batch,
                purchase_date=item["purchase_date"],
                statement_year=item["statement_year"],
                statement_month=item["statement_month"],
                description=item["description"],
                amount=item["amount"],
                installments_total=item.get("installments_total", 1) or 1,
                installments_current=item.get("installments_current"),
                purchase_flag=item.get("purchase_flag", "UNKNOWN"),
                purchase_prefix_raw=item.get("purchase_prefix_raw", ""),
                purchase_type_raw=item.get("purchase_type_raw", ""),
            )
        )
    return created_items
