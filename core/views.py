from calendar import monthrange
from datetime import date

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CardForm, CardPurchaseForm, RecurringExpenseForm
from .models import CardPurchase, RecurringExpense


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

    card_purchases = CardPurchase.objects.select_related("cartao").order_by("primeiro_vencimento")
    installments = []
    for purchase in card_purchases:
        diff = (year - purchase.primeiro_vencimento.year) * 12 + (month - purchase.primeiro_vencimento.month)
        if 0 <= diff < purchase.parcelas:
            vencimento = _add_months(purchase.primeiro_vencimento, diff)
            installments.append(
                {
                    "cartao": purchase.cartao.nome,
                    "descricao": purchase.descricao,
                    "parcela_atual": diff + 1,
                    "parcelas": purchase.parcelas,
                    "valor": purchase.valor_parcela,
                    "vencimento": vencimento,
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
                "descricao": conta.descricao,
                "valor": conta.valor,
                "vencimento": vencimento,
            }
        )

    total_card = sum(item["valor"] for item in installments)
    total_recurring = sum(item["valor"] for item in recurring_items)
    total_month = total_card + total_recurring

    previous_month = _add_months(month_start, -1).strftime("%Y-%m")
    next_month = _add_months(month_start, 1).strftime("%Y-%m")

    context = {
        "month_start": month_start,
        "month_end": month_end,
        "installments": installments,
        "recurring_items": recurring_items,
        "total_card": total_card,
        "total_recurring": total_recurring,
        "total_month": total_month,
        "card_form": card_form,
        "purchase_form": purchase_form,
        "recurring_form": recurring_form,
        "previous_month": previous_month,
        "next_month": next_month,
    }
    return render(request, "core/dashboard.html", context)
