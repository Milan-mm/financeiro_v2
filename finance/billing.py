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


def get_first_installment_due_date(
    purchase_date: date,
    closing_day: int,
) -> date:
    """
    Calcula a data de vencimento esperada da PRIMEIRA parcela.
    
    Para uma compra em 25/09/2025 com parcelamento, a primeira parcela
    deveria vencer no mês seguinte (outubro/2025) no mesmo dia de fechamento
    do cartão.
    
    Args:
        purchase_date: Data da compra original
        closing_day: Dia de fechamento do cartão
    
    Returns:
        Data de vencimento da primeira parcela
    """
    # Próximo mês após a compra
    year = purchase_date.year
    month = purchase_date.month + 1
    if month > 12:
        month = 1
        year += 1
    
    # Primeira parcela vence no dia de fechamento do próximo mês
    result = normalize_day(year, month, closing_day)
    print(f"[GET_FIRST_INSTALLMENT_DUE_DATE] purchase={purchase_date}, closing_day={closing_day} -> first_due={result}")
    return result

