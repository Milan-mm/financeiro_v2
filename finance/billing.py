from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def last_day_of_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def normalize_day(year: int, month: int, day: int) -> date:
    safe_day = min(day, last_day_of_month(year, month))
    return date(year, month, safe_day)


def get_statement_window(statement_year: int, statement_month: int, closing_day: int):
    closing_date = normalize_day(statement_year, statement_month, closing_day)
    previous_month = 12 if statement_month == 1 else statement_month - 1
    previous_year = statement_year - 1 if statement_month == 1 else statement_year
    previous_closing = normalize_day(previous_year, previous_month, closing_day)
    period_start = previous_closing + timedelta(days=1)
    period_end = closing_date
    return closing_date, period_start, period_end


def get_due_date(statement_year: int, statement_month: int, due_day: int) -> date:
    return normalize_day(statement_year, statement_month, due_day)
