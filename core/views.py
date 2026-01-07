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
from .models import Card, CardPurchase, RecurringExpense, RecurringPayment, Category, SystemLog


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

    # Busca as compras
    card_purchases = (
        CardPurchase.objects.select_related("cartao")
        .filter(user=user)
        .order_by("primeiro_vencimento")
    )
    purchases = []

    for purchase in card_purchases:
        diff = (year - purchase.primeiro_vencimento.year) * 12 + (month - purchase.primeiro_vencimento.month)

        # Verifica se a parcela deve ser mostrada neste mês
        if 0 <= diff < purchase.parcelas:
            vencimento = _add_months(purchase.primeiro_vencimento, diff)

            # LÓGICA DE PROTEÇÃO AQUI
            # Se tiver cartão, usa o nome. Se não tiver (ex: Débito), usa "Débito / À Vista"
            if purchase.cartao:
                nome_origem = purchase.cartao.nome
            else:
                nome_origem = "Débito / À Vista"

            purchases.append(
                {
                    "id": purchase.id,
                    "cartao_id": purchase.cartao_id,
                    "cartao_nome": nome_origem,  # Usamos a variável protegida aqui
                    "descricao": purchase.descricao,
                    "parcela_atual": diff + 1,
                    "parcelas": purchase.parcelas,
                    "valor_parcela": float(purchase.valor_parcela),
                    "valor_total": float(purchase.valor_total),
                    "primeiro_vencimento": purchase.primeiro_vencimento.isoformat(),
                    "vencimento": vencimento.isoformat(),
                }
            )

    # Processamento de Recorrentes (Contas fixas)
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

    # Cálculos dos Totais
    total_card = sum(item["valor_parcela"] for item in purchases)
    total_recurring = sum(item["valor"] for item in recurring_items)
    total_month = total_card + total_recurring

    # Agrupamento por Cartão (para os totais no topo da dashboard)
    cards = []
    # Nota: Aqui filtramos Card.objects, então só vai mostrar totais de cartões que realmente existem
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


# 1. API para Marcar como Pago
@login_required
@require_http_methods(["POST"])
def pay_recurring_api(request, pk):
    try:
        data = json.loads(request.body)
        year = int(data.get("year"))
        month = int(data.get("month"))

        expense = RecurringExpense.objects.get(pk=pk, user=request.user)

        # Cria ou atualiza o registo de pagamento para este mês
        payment, created = RecurringPayment.objects.get_or_create(
            expense=expense,
            year=year,
            month=month,
            defaults={"is_paid": True}
        )

        if not created:
            payment.is_paid = True
            payment.save()

        return JsonResponse({"status": "ok"})
    except RecurringExpense.DoesNotExist:
        return JsonResponse({"error": "Conta não encontrada"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# 2. API para Atualizar o Valor
@login_required
@require_http_methods(["POST"])
def update_recurring_value_api(request, pk):
    try:
        data = json.loads(request.body)
        novo_valor = data.get("valor")

        if novo_valor is None:
            return JsonResponse({"error": "Valor não fornecido"}, status=400)

        expense = RecurringExpense.objects.get(pk=pk, user=request.user)
        expense.valor = novo_valor
        expense.save()

        return JsonResponse({"status": "ok", "novo_valor": expense.valor})
    except RecurringExpense.DoesNotExist:
        return JsonResponse({"error": "Conta não encontrada"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


import json
import logging
import uuid
from decimal import Decimal
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .installments import calculate_installment_values
from .utils_ai import analyze_invoice_text
from .models import CardPurchase, Card, Category

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def parse_invoice_api(request):
    """Recebe o texto bruto e devolve o JSON da IA para revisão."""
    try:
        body = json.loads(request.body)
        text = body.get('text', '')

        if not text:
            return JsonResponse({"error": "Texto vazio"}, status=400)

        data = analyze_invoice_text(text)
        return JsonResponse(data, safe=False)
    except Exception:
        error_id = uuid.uuid4().hex
        logger.exception("Erro ao processar importação via IA [error_id=%s]", error_id)
        return JsonResponse(
            {"error": "Erro ao analisar importação", "error_id": error_id},
            status=500,
        )


@login_required
@require_http_methods(["POST"])
def batch_create_purchases_api(request):
    """Salva a lista revisada no banco de dados."""
    context_info = {}
    try:
        data = json.loads(request.body)
        card_id = data.get('card_id')
        items = data.get('items', [])

        if not card_id or not items:
            return JsonResponse({"error": "Dados incompletos"}, status=400)

        card = Card.objects.get(id=card_id, user=request.user)

        saved_count = 0

        with transaction.atomic():
            for item in items:
                descricao = item.get("descricao")
                valor = item.get("valor")
                data_compra = item.get("data")
                parcelas = item.get("parcelas", 1)

                if not descricao or valor is None or not data_compra:
                    raise ValueError("Item inválido: descricao, valor e data são obrigatórios.")

                valor_decimal = Decimal(str(valor))
                valor_total_compra = item.get("valor_total_compra") or item.get("valor_total_da_compra")

                context_info = {
                    "descricao": str(descricao)[:60],
                    "data": data_compra,
                    "parcelas": parcelas,
                    "valor": str(valor_decimal),
                    "valor_total_compra": valor_total_compra,
                    "regra": None,
                }

                category = None
                if item.get("category_id"):
                    try:
                        category = Category.objects.get(
                            id=item["category_id"],
                            user=request.user,
                        )
                    except Category.DoesNotExist:
                        raise ValueError("Categoria inválida para o usuário.")

                valor_total, _valor_parcela, regra = calculate_installment_values(
                    valor_decimal,
                    parcelas,
                    valor_total_compra=valor_total_compra,
                )
                context_info["regra"] = regra

                CardPurchase.objects.create(
                    user=request.user,
                    cartao=card,
                    descricao=descricao,
                    valor_total=valor_total,
                    parcelas=parcelas,
                    primeiro_vencimento=data_compra,  # O front deve mandar a data correta
                    categoria=category,
                    tipo_pagamento="CREDITO",  # Assumindo crédito para importação de fatura
                )
                saved_count += 1

        total_now = CardPurchase.objects.filter(user=request.user, cartao=card).count()
        return JsonResponse(
            {
                "status": "ok",
                "count": saved_count,
                "total_now": total_now,
                "handler": "batch_create_purchases_api_v2",
            }
        )

    except Card.DoesNotExist:
        return JsonResponse({"error": "Cartão não encontrado"}, status=404)
    except Exception:
        error_id = uuid.uuid4().hex[:10]
        logger.exception(
            "IMPORT_SAVE_FAILED error_id=%s user_id=%s card_id=%s items=%s context=%s",
            error_id,
            request.user.id,
            card_id,
            len(items) if isinstance(items, list) else None,
            context_info,
        )
        return JsonResponse(
            {"error": "Falha ao salvar importação", "error_id": error_id},
            status=500,
        )

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


@login_required
def system_logs_view(request):
    return render(request, "core/system_logs.html")


@require_http_methods(["POST"])
def log_error_api(request):
    payload = _json_body(request)
    message = payload.get("message") or "Erro no frontend"
    details = payload.get("details") or ""
    level = payload.get("level") or SystemLog.LEVEL_ERROR
    if level not in {choice[0] for choice in SystemLog.LEVEL_CHOICES}:
        level = SystemLog.LEVEL_ERROR

    SystemLog.objects.create(
        level=level,
        source=SystemLog.SOURCE_FRONTEND,
        message=message[:255],
        details=details,
    )
    return JsonResponse({"created": True})


@login_required
@require_http_methods(["GET"])
def system_logs_api(request):
    logs = SystemLog.objects.all()
    data = [
        {
            "id": log.id,
            "level": log.level,
            "level_label": log.get_level_display(),
            "source": log.source,
            "source_label": log.get_source_display(),
            "message": log.message,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
            "is_resolved": log.is_resolved,
        }
        for log in logs
    ]
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def system_log_detail_api(request, log_id):
    log = get_object_or_404(SystemLog, pk=log_id)
    if request.method == "DELETE":
        log.delete()
        return JsonResponse({"deleted": True})

    payload = _json_body(request)
    is_resolved = payload.get("is_resolved")
    if is_resolved is None:
        is_resolved = True
    log.is_resolved = bool(is_resolved)
    log.save(update_fields=["is_resolved"])
    return JsonResponse({"updated": True, "is_resolved": log.is_resolved})


@login_required
@require_http_methods(["GET"])
def system_logs_pending_count_api(request):
    count = SystemLog.objects.filter(is_resolved=False).count()
    return JsonResponse({"pending": count})

import logging
import re
from decimal import Decimal
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.core.cache import cache
from django.contrib.auth.models import User
from twilio.twiml.messaging_response import MessagingResponse

from core.models import QuickExpense

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def twilio_webhook(request):
    # Normaliza a mensagem para facilitar comparação
    incoming_msg = request.POST.get('Body', '').strip().lower()
    sender = request.POST.get('From')

    # Identificação do usuário (ajuste conforme sua lógica de segurança)
    user = User.objects.first()

    # Prepara objeto de resposta Twilio
    resp = MessagingResponse()

    # Controle de Estado via Cache (Redis/LocMem)
    cache_key = f"whatsapp_state_{sender}"
    state = cache.get(cache_key)

    # =========================================================================
    # 1. COMANDO MESTRE: MENU (Reseta tudo e mostra opções)
    # =========================================================================
    if incoming_msg == 'menu':
        cache.delete(cache_key)  # Zera qualquer estado anterior para evitar travas
        msg = resp.message()
        msg.body(
            "🤖 *Financeiro Bot*\n"
            "━━━━━━━━━━━━━━━━\n"
            "1️⃣  Lançar Gasto\n"
            "2️⃣  Resumo do Mês\n"
            "3️⃣  Cancelar\n"
            "━━━━━━━━━━━━━━━━\n"
            "Selecione uma opção:"
        )
        return HttpResponse(str(resp))

    # =========================================================================
    # 2. COMANDO: CANCELAR
    # =========================================================================
    if incoming_msg == '3':
        cache.delete(cache_key)
        msg = resp.message()
        msg.body("❌ Operação cancelada. Nada foi salvo.")
        return HttpResponse(str(resp))

    # =========================================================================
    # 3. FLUXO: INICIAR LANÇAMENTO (Envia Template)
    # =========================================================================
    if incoming_msg == '1' and state is None:
        msg = resp.message()
        # UX: Envia o formato exato para o usuário apenas copiar e editar
        msg.body(
            "📋 *Novo Gasto*\n"
            "Copie a mensagem abaixo, preencha e envie:\n\n"
            "D: \n"
            "V: "
        )
        # Define estado de espera pelo preenchimento
        cache.set(cache_key, 'WAITING_DATA', timeout=600)  # 10 minutos
        return HttpResponse(str(resp))

    # =========================================================================
    # 4. FLUXO: RESUMO DO MÊS
    # =========================================================================
    if incoming_msg == '2' and state is None:
        from django.utils import timezone
        hoje = timezone.now()

        total = QuickExpense.objects.filter(
            user=user,
            data__month=hoje.month,
            data__year=hoje.year
        ).aggregate(Sum('valor'))['valor__sum'] or 0

        msg = resp.message()
        msg.body(f"📊 *Resumo de {hoje.strftime('%B').capitalize()}*\n\n💰 Total Rápido: *R$ {total:.2f}*")
        return HttpResponse(str(resp))

    # =========================================================================
    # 5. PROCESSAMENTO DE DADOS (Quando o usuário envia o template preenchido)
    # =========================================================================
    if state == 'WAITING_DATA':
        # Regex para capturar Descrição (D:) e Valor (V:) em qualquer ordem/case
        # Padrão D: pega tudo até a quebra de linha ou próximo comando V:
        match_desc = re.search(r'd:\s*(.*?)(?:\n|v:|$)', incoming_msg, re.IGNORECASE | re.DOTALL)
        # Padrão V: pega números, pontos e vírgulas
        match_val = re.search(r'v:\s*([\d\.,]+)', incoming_msg, re.IGNORECASE)

        if match_desc and match_val:
            try:
                raw_desc = match_desc.group(1).strip()
                raw_val = match_val.group(1).replace(',', '.')

                if not raw_desc:
                    raw_desc = "Gasto Rápido"

                valor_final = Decimal(raw_val)

                # Salva no Banco
                QuickExpense.objects.create(
                    user=user,
                    descricao=raw_desc.title(),
                    valor=valor_final
                )

                # Sucesso
                cache.delete(cache_key)
                msg = resp.message()
                msg.body(f"✅ *Lançado!*\n{raw_desc.title()} - R$ {valor_final:.2f}")
                return HttpResponse(str(resp))

            except Exception:
                # Erro de conversão de valor (ex: digitou letras no valor)
                msg = resp.message()
                msg.body(
                    "⚠️ Valor inválido.\nCertifique-se de colocar apenas números após o 'V:'.\nTente novamente ou digite *menu*.")
                return HttpResponse(str(resp))
        else:
            # Usuário mandou algo que não segue o padrão D: / V:
            msg = resp.message()
            msg.body("⚠️ Formato não reconhecido.\nCopie o modelo (D: ... V: ... ) e tente novamente.")
            return HttpResponse(str(resp))

    # =========================================================================
    # 6. MODO FURTIVO (DEFAULT)
    # =========================================================================
    # Se chegou aqui, não é 'menu', não é opção válida e não estamos esperando dados.
    # Retorna XML vazio para o Twilio. O usuário não recebe NADA.
    return HttpResponse(str(resp))