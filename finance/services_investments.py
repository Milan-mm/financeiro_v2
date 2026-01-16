from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .models import InvestmentSnapshot


@dataclass(frozen=True)
class MonthlyDelta:
    month: int
    total: Decimal
    delta_abs: Decimal | None
    delta_pct: Decimal | None


def get_investment_snapshots(household, year: int):
    return (
        InvestmentSnapshot.objects.filter(household=household, year=year)
        .select_related("account")
        .order_by("account__name", "month")
    )


def compute_monthly_totals(snapshots) -> list[Decimal]:
    totals = [Decimal("0.00") for _ in range(12)]
    for snapshot in snapshots:
        if 1 <= snapshot.month <= 12:
            totals[snapshot.month - 1] += snapshot.balance
    return totals


def compute_mom_deltas(series: list[Decimal]) -> list[MonthlyDelta]:
    deltas: list[MonthlyDelta] = []
    previous = None
    for idx, current in enumerate(series, start=1):
        if previous is None:
            deltas.append(MonthlyDelta(month=idx, total=current, delta_abs=None, delta_pct=None))
            previous = current
            continue

        delta_abs = current - previous
        if previous == 0 and current == 0:
            delta_pct = Decimal("0.00")
        elif previous == 0 and current != 0:
            delta_pct = None
        else:
            delta_pct = (delta_abs / previous) * Decimal("100.00")
        deltas.append(
            MonthlyDelta(
                month=idx,
                total=current,
                delta_abs=delta_abs,
                delta_pct=delta_pct,
            )
        )
        previous = current
    return deltas


def compute_account_series(snapshots) -> dict[int, list[Decimal]]:
    account_series: dict[int, list[Decimal]] = defaultdict(lambda: [Decimal("0.00") for _ in range(12)])
    for snapshot in snapshots:
        if 1 <= snapshot.month <= 12:
            account_series[snapshot.account_id][snapshot.month - 1] = snapshot.balance
    return account_series
