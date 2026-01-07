from calendar import monthrange
from datetime import date
import json

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CardForm, CardPurchaseForm, RecurringExpenseForm, UserRegisterForm
from .models import Card, CardPurchase, RecurringExpense, RecurringPayment, Category


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


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


def _add_months(base_date, months):
    total_month = base_date.month - 1 + months
    year = base_date.year + total_month // 12
    month = total_month % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _build_month_data(user, year, month):
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    card_purchases = (
        CardPurchase.objects.select_related("cartao")
        .filter(user=user)
        .order_by("primeiro_vencimento")
    )
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
    recurring_queryset = RecurringExpense.objects.filter(user=user, ativo=True).order_by("dia_vencimento")
    recurring_payments = RecurringPayment.objects.filter(
        expense__in=recurring_queryset,
        year=year,
        month=month,
    )
    payments_by_expense = {payment.expense_id: payment for payment in recurring_payments}
    for conta in recurring_queryset:
        if conta.inicio > month_end:
            continue
        if conta.fim and conta.fim < month_start:
            continue
        due_day = min(conta.dia_vencimento, monthrange(year, month)[1])
        vencimento = date(year, month, due_day)
        payment = payments_by_expense.get(conta.id)
        recurring_items.append(
            {
                "id": conta.id,
                "descricao": conta.descricao,
                "categoria_nome": conta.categoria.nome if conta.categoria else None,
                "valor": float(conta.valor),
                "dia_vencimento": conta.dia_vencimento,
                "inicio": conta.inicio.isoformat(),
                "fim": conta.fim.isoformat() if conta.fim else None,
                "ativo": conta.ativo,
                "vencimento": vencimento.isoformat(),
                "is_paid": bool(payment.is_paid) if payment else False,
            }
        )

    total_card = sum(item["valor_parcela"] for item in purchases)
    total_recurring = sum(item["valor"] for item in recurring_items)
    total_month = total_card + total_recurring

    cards = []
    for card in Card.objects.filter(user=user, ativo=True).order_by("nome"):
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
    purchase_form.fields["cartao"].queryset = Card.objects.filter(user=request.user)
    recurring_form = RecurringExpenseForm(prefix="recurring")

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "card":
            card_form = CardForm(request.POST, prefix="card")
            if card_form.is_valid():
                card_form.instance.user = request.user
                card_form.save()
                messages.success(request, "Cartão cadastrado com sucesso.")
                return redirect("dashboard")
        elif form_type == "purchase":
            purchase_form = CardPurchaseForm(request.POST, prefix="purchase")
            purchase_form.fields["cartao"].queryset = Card.objects.filter(user=request.user)
            if purchase_form.is_valid():
                purchase_form.instance.user = request.user
                purchase_form.save()
                messages.success(request, "Compra lançada com sucesso.")
                return redirect("dashboard")
        elif form_type == "recurring":
            recurring_form = RecurringExpenseForm(request.POST, prefix="recurring")
            if recurring_form.is_valid():
                recurring_form.instance.user = request.user
                recurring_form.save()
                messages.success(request, "Conta recorrente cadastrada com sucesso.")
                return redirect("dashboard")

    month_data = _build_month_data(request.user, year, month)

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
def cards_view(request):
    form = CardForm(prefix="card")
    cards = Card.objects.filter(user=request.user).order_by("nome")
    if request.method == "POST":
        form = CardForm(request.POST, prefix="card")
        if form.is_valid():
            form.instance.user = request.user
            form.save()
            messages.success(request, "Cartão cadastrado com sucesso.")
            return redirect("cards")
    return render(
        request,
        "core/cards.html",
        {
            "cards": cards,
            "card_form": form,
        },
    )


@login_required
def expenses_view(request):
    today = date.today()
    month_param = request.GET.get("month")
    if month_param:
        year, month = [int(part) for part in month_param.split("-")]
    else:
        year, month = today.year, today.month

    month_data = _build_month_data(request.user, year, month)
    context = {
        "month_start": date(year, month, 1),
        "installments": month_data["purchases"],
        "recurring_items": month_data["recurring"],
        "total_card": month_data["totals"]["total_card"],
        "total_recurring": month_data["totals"]["total_recurring"],
        "total_month": month_data["totals"]["total_month"],
    }
    return render(request, "core/expenses.html", context)


# 2. Atualiza a função settings_view com esta nova versão completa
@login_required
def settings_view(request):
    register_form = UserRegisterForm(prefix="register")

    if request.method == "POST":
        action = request.POST.get("action")

        # Lógica de CADASTRO (que já tinhas)
        if action == "register":
            register_form = UserRegisterForm(request.POST, prefix="register")
            if register_form.is_valid():
                register_form.save()
                messages.success(request, "Novo usuário adicionado com sucesso.")
                return redirect("settings")
            else:
                messages.error(request, "Erro ao adicionar usuário. Verifique os dados.")

        # NOVA Lógica de EXCLUSÃO
        elif action == "delete_user":
            user_id = request.POST.get("user_id")
            try:
                user_to_delete = User.objects.get(pk=user_id)
                # Segurança: Impede que te excluas a ti próprio
                if user_to_delete == request.user:
                    messages.error(request, "Você não pode excluir o seu próprio usuário.")
                else:
                    email_removido = user_to_delete.email or user_to_delete.username
                    user_to_delete.delete()
                    messages.success(request, f"Usuário {email_removido} removido com sucesso.")
            except User.DoesNotExist:
                messages.error(request, "Usuário não encontrado.")
            return redirect("settings")

    # Busca todos os usuários, menos o logado atual, para preencher a lista
    users = User.objects.exclude(pk=request.user.pk).order_by('username')

    return render(request, "core/settings.html", {
        "register_form": register_form,
        "users": users,  # Enviamos a lista para o template
    })


@login_required
@require_http_methods(["GET"])
def month_data_api(request):
    try:
        year = int(request.GET.get("year"))
        month = int(request.GET.get("month"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ano e mês inválidos."}, status=400)

    data = _build_month_data(request.user, year, month)
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
    form.fields["cartao"].queryset = Card.objects.filter(user=request.user)
    if form.is_valid():
        form.instance.user = request.user
        purchase = form.save()
        return JsonResponse({"id": purchase.id}, status=201)
    return JsonResponse({"error": "Dados inválidos.", "details": form.errors}, status=400)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def card_purchase_detail_api(request, purchase_id):
    purchase = get_object_or_404(CardPurchase, pk=purchase_id, user=request.user)
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
    form.fields["cartao"].queryset = Card.objects.filter(user=request.user)
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
        form.instance.user = request.user
        expense = form.save()
        return JsonResponse({"id": expense.id}, status=201)
    return JsonResponse({"error": "Dados inválidos.", "details": form.errors}, status=400)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def recurring_expense_detail_api(request, expense_id):
    expense = get_object_or_404(RecurringExpense, pk=expense_id, user=request.user)
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

@login_required
@require_http_methods(["GET"])
def categories_api(request):
    cats = Category.objects.filter(user=request.user).order_by('nome')
    data = [{"id": c.id, "nome": c.nome, "cor": c.cor} for c in cats]
    return JsonResponse(data, safe=False)

@login_required
@require_http_methods(["POST"])
def recurring_payment_toggle_api(request):
    payload = _json_body(request)
    try:
        expense_id = int(payload.get("expense_id"))
        year = int(payload.get("year"))
        month = int(payload.get("month"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Dados inválidos."}, status=400)

    if month < 1 or month > 12:
        return JsonResponse({"error": "Mês inválido."}, status=400)

    expense = get_object_or_404(RecurringExpense, pk=expense_id, user=request.user)
    payment, created = RecurringPayment.objects.get_or_create(
        expense=expense,
        year=year,
        month=month,
    )
    if created:
        payment.is_paid = True
    else:
        payment.is_paid = not payment.is_paid
    payment.save(update_fields=["is_paid", "paid_at"])
    return JsonResponse({"is_paid": payment.is_paid})
