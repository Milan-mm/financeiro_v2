from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


def calculate_installment_values(valor, parcelas, valor_total_compra=None):
    """
    Regra de importação de parcelados:
    - Se qtd_parcelas > 1 e NÃO houver valor_total_compra explícito, assume-se que
      o valor informado já é o valor da parcela lançada na fatura.
    - Se houver valor_total_compra explícito, calcula-se a parcela dividindo o total.
    - Para 1x, o valor da parcela e o total são iguais.
    """
    parcelas = int(parcelas or 1)
    if parcelas <= 0:
        parcelas = 1

    valor_parcela = _quantize_money(_to_decimal(valor))

    if parcelas == 1:
        return valor_parcela, valor_parcela, "avista"

    if valor_total_compra is not None:
        valor_total = _quantize_money(_to_decimal(valor_total_compra))
        valor_parcela = _quantize_money(valor_total / Decimal(parcelas))
        return valor_total, valor_parcela, "total_informado"

    valor_total = _quantize_money(valor_parcela * Decimal(parcelas))
    return valor_total, valor_parcela, "parcela_informada"
