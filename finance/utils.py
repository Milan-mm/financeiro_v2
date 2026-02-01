from __future__ import annotations

import hashlib
import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import date


_TWOPLACES = Decimal("0.01")
_SPACE_RE = re.compile(r"\s+")


def normalize_description(description: str) -> str:
    cleaned = description.strip().upper()
    return _SPACE_RE.sub(" ", cleaned)


def build_installment_logical_key(
    description: str,
    purchase_date: date,
    amount: Decimal,
    installments_total: int,
) -> str:
    normalized_description = normalize_description(description)
    normalized_amount = Decimal(amount).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    payload = f"{normalized_description}|{purchase_date.isoformat()}|{normalized_amount:.2f}|{int(installments_total)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
