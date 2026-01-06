from calendar import monthrange
from datetime import date
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CardForm, CardPurchaseForm, RecurringExpenseForm
from .models import Card, CardPurchase, RecurringExpense


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Usuário ou senha inválidos.")

    return render(request, "core/login.html")


def _add_months(base_date, months):
    total_month = base_date.month - 1 + months
    year = base_date.year + total_month // 12
    month = total_month % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _build_month_data(year, month):
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    card_purchases = CardPurchase.objects.select_related("cartao").order_by("primeiro_vencimento")
    purchases = []
    for purchase in card_purchases:
        diff = (year - purchase.primeiro_vencimento.year) * 12 + (month - purchase.primeiro_vencimento.month)
        if 0 <= diff < purchase.parcelas:
            vencimento = _add_months(purchase.primeiro_vencimento, diff)
            purchases.append(
                {
                    "id": purchase.id,
                    "cartao_id": purchase.cartao_id,
                    "cartao_nome": purchase.cartao.nome,
                    "descricao": purchase.descricao,
                    "parcela_atual": diff + 1,
                    "parcelas": purchase.parcelas,
                    "valor_parcela": float(purchase.valor_parcela),
                    "valor_total": float(purchase.valor_total),
                    "primeiro_vencimento": purchase.primeiro_vencimento.isoformat(),
                    "vencimento": vencimento.isoformat(),
                }
            )

    recurring_items = []
    for conta in RecurringExpense.objects.filter(ativo=True).order_by("dia_vencimento"):
        if conta.inicio > month_end:
            continue
        if conta.fim and conta.fim < month_start:
            continue
        due_day = min(conta.dia_vencimento, monthrange(year, month)[1])
        vencimento = date(year, month, due_day)
        recurring_items.append(
            {
                "id": conta.id,
                "descricao": conta.descricao,
                "valor": float(conta.valor),
                "dia_vencimento": conta.dia_vencimento,
                "inicio": conta.inicio.isoformat(),
                "fim": conta.fim.isoformat() if conta.fim else None,
                "ativo": conta.ativo,
                "vencimento": vencimento.isoformat(),
            }
        )

    total_card = sum(item["valor_parcela"] for item in purchases)
    total_recurring = sum(item["valor"] for item in recurring_items)
    total_month = total_card + total_recurring

    cards = []
    for card in Card.objects.filter(ativo=True).order_by("nome"):
        total_mes = sum(item["valor_parcela"] for item in purchases if item["cartao_id"] == card.id)
        cards.append(
            {
                "id": card.id,
                "nome": card.nome,
                "ativo": card.ativo,
                "total_mes": float(total_mes),
            }
        )

    return {
        "month_start": month_start,
        "month_end": month_end,
        "totals": {
            "total_card": float(total_card),
            "total_recurring": float(total_recurring),
            "total_month": float(total_month),
        },
        "cards": cards,
        "purchases": purchases,
        "recurring": recurring_items,
    }


@login_required
def dashboard(request):
    today = date.today()
    month_param = request.GET.get("month")
    if month_param:
        year, month = [int(part) for part in month_param.split("-")]
    else:
        year, month = today.year, today.month

    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    card_form = CardForm(prefix="card")
    purchase_form = CardPurchaseForm(prefix="purchase")
    recurring_form = RecurringExpenseForm(prefix="recurring")

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "card":
            card_form = CardForm(request.POST, prefix="card")
            if card_form.is_valid():
                card_form.save()
                messages.success(request, "Cartão cadastrado com sucesso.")
                return redirect("dashboard")
        elif form_type == "purchase":
            purchase_form = CardPurchaseForm(request.POST, prefix="purchase")
            if purchase_form.is_valid():
                purchase_form.save()
                messages.success(request, "Compra lançada com sucesso.")
                return redirect("dashboard")
        elif form_type == "recurring":
            recurring_form = RecurringExpenseForm(request.POST, prefix="recurring")
            if recurring_form.is_valid():
                recurring_form.save()
                messages.success(request, "Conta recorrente cadastrada com sucesso.")
                return redirect("dashboard")

    month_data = _build_month_data(year, month)

    previous_month = _add_months(month_start, -1).strftime("%Y-%m")
    next_month = _add_months(month_start, 1).strftime("%Y-%m")

    context = {
        "month_start": month_start,
        "month_end": month_end,
        "installments": month_data["purchases"],
        "recurring_items": month_data["recurring"],
        "total_card": month_data["totals"]["total_card"],
        "total_recurring": month_data["totals"]["total_recurring"],
        "total_month": month_data["totals"]["total_month"],
        "card_form": card_form,
        "purchase_form": purchase_form,
        "recurring_form": recurring_form,
        "previous_month": previous_month,
        "next_month": next_month,
    }
    return render(request, "core/dashboard.html", context)


@login_required
@require_http_methods(["GET"])
def month_data_api(request):
    try:
        year = int(request.GET.get("year"))
        month = int(request.GET.get("month"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ano e mês inválidos."}, status=400)

    data = _build_month_data(year, month)
    response = {
        "year": year,
        "month": month,
        "totals": data["totals"],
        "cards": data["cards"],
        "purchases": data["purchases"],
        "recurring": data["recurring"],
    }
    return JsonResponse(response)


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


@login_required
@require_http_methods(["POST"])
def card_purchase_create_api(request):
    payload = _json_body(request)
    if "cartao_id" in payload:
        payload["cartao"] = payload.pop("cartao_id")
    form = CardPurchaseForm(payload)
    if form.is_valid():
        purchase = form.save()
        return JsonResponse({"id": purchase.id}, status=201)
    return JsonResponse({"error": "Dados inválidos.", "details": form.errors}, status=400)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def card_purchase_detail_api(request, purchase_id):
    purchase = get_object_or_404(CardPurchase, pk=purchase_id)
    if request.method == "DELETE":
        purchase.delete()
        return JsonResponse({"deleted": True})

    payload = _json_body(request)
    if "cartao_id" in payload:
        payload["cartao"] = payload.pop("cartao_id")

    data = {
        "cartao": purchase.cartao_id,
        "descricao": purchase.descricao,
        "valor_total": purchase.valor_total,
        "parcelas": purchase.parcelas,
        "primeiro_vencimento": purchase.primeiro_vencimento,
    }
    data.update(payload)
    form = CardPurchaseForm(data, instance=purchase)
    if form.is_valid():
        form.save()
        return JsonResponse({"updated": True})
    return JsonResponse({"error": "Dados inválidos.", "details": form.errors}, status=400)


@login_required
@require_http_methods(["POST"])
def recurring_expense_create_api(request):
    payload = _json_body(request)
    form = RecurringExpenseForm(payload)
    if form.is_valid():
        expense = form.save()
        return JsonResponse({"id": expense.id}, status=201)
    return JsonResponse({"error": "Dados inválidos.", "details": form.errors}, status=400)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def recurring_expense_detail_api(request, expense_id):
    expense = get_object_or_404(RecurringExpense, pk=expense_id)
    if request.method == "DELETE":
        expense.delete()
        return JsonResponse({"deleted": True})

    payload = _json_body(request)
    data = {
        "descricao": expense.descricao,
        "valor": expense.valor,
        "dia_vencimento": expense.dia_vencimento,
        "inicio": expense.inicio,
        "fim": expense.fim,
        "ativo": expense.ativo,
    }
    data.update(payload)
    form = RecurringExpenseForm(data, instance=expense)
    if form.is_valid():
        form.save()
        return JsonResponse({"updated": True})
    return JsonResponse({"error": "Dados inválidos.", "details": form.errors}, status=400)
