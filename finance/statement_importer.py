from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .billing import get_statement_window


HEADER_RE = re.compile(r"Compra\s+Data\s+Descrição", re.IGNORECASE)
DATE_RE = re.compile(r"\b(\d{2})/(\d{2})\b")
AMOUNT_RE = re.compile(r"(-?\d{1,3}(?:\.\d{3})*,\d{2})")
INSTALLMENT_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")


class PurchaseFlag:
    APPROX = "APPROX"
    ONLINE = "ONLINE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ParsedStatementItem:
    raw_line: str
    prefix_raw: str | None
    flag: str
    purchase_date: date
    statement_year: int
    statement_month: int
    installments_total: int
    installments_current: int | None
    description: str
    amount: Decimal
    ledger_date: date
    inference_note: str


def _infer_year(statement_year: int, statement_month: int, line_month: int) -> tuple[int, str]:
    if line_month > statement_month:
        return statement_year - 1, f"line_month={line_month} > statement_month={statement_month} => year={statement_year - 1}"
    return statement_year, f"line_month={line_month} <= statement_month={statement_month} => year={statement_year}"


def _parse_amounts(text: str) -> list[Decimal]:
    amounts = []
    for match in AMOUNT_RE.findall(text):
        normalized = match.replace(".", "").replace(",", ".")
        amounts.append(Decimal(normalized))
    return amounts


def parse_statement_text(
    text: str,
    statement_year: int,
    statement_month: int,
    closing_day: int,
) -> list[ParsedStatementItem]:
    items: list[ParsedStatementItem] = []
    if not text:
        return items

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if HEADER_RE.search(line):
            continue
        if line.lower().startswith("parcelamentos"):
            continue
        date_match = DATE_RE.search(line)
        if not date_match:
            continue

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        inferred_year, note = _infer_year(statement_year, statement_month, month)
        purchase_date = date(inferred_year, month, day)

        prefix_part = line[: date_match.start()].strip()
        prefix_raw = prefix_part if prefix_part else None
        if prefix_raw == "3":
            flag = PurchaseFlag.APPROX
        elif prefix_raw == "2":
            flag = PurchaseFlag.ONLINE
        else:
            flag = PurchaseFlag.UNKNOWN

        rest = line[date_match.end() :].strip()
        installments_current = None
        installments_total = 1
        for match in INSTALLMENT_RE.findall(rest):
            current = int(match[0])
            total = int(match[1])
            if total > 1:
                installments_current = current
                installments_total = total
                break

        amounts = _parse_amounts(rest)
        if not amounts:
            continue
        amount = amounts[-1] if len(amounts) == 1 else amounts[-2]

        description = rest
        for installment_match in INSTALLMENT_RE.findall(rest):
            marker = f"{installment_match[0]}/{installment_match[1]}"
            description = description.replace(marker, "").strip()
        for amount_match in AMOUNT_RE.findall(description):
            description = description.replace(amount_match, "").strip()
        description = re.sub(r"\s{2,}", " ", description)

        closing_date, _, _ = get_statement_window(statement_year, statement_month, closing_day)

        items.append(
            ParsedStatementItem(
                raw_line=raw_line,
                prefix_raw=prefix_raw,
                flag=flag,
                purchase_date=purchase_date,
                statement_year=statement_year,
                statement_month=statement_month,
                installments_total=installments_total,
                installments_current=installments_current,
                description=description,
                amount=amount,
                ledger_date=closing_date,
                inference_note=note,
            )
        )

    return items
