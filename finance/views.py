from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .billing import get_due_date, get_statement_window
from .statement_importer import parse_statement_text
from .forms import (
    AccountForm,
    CardForm,
    CardPurchaseGroupForm,
    CategoryForm,
    ImportPasteForm,
    ImportReviewFormSet,
    LedgerEntryForm,
    InvestmentAccountForm,
    InvestmentSnapshotForm,
    ReceivableForm,
    RecurringInstanceValueOverrideForm,
    RecurringRuleForm,
)
from .models import (
    Account,
    Card,
    CardPurchaseGroup,
    Category,
    ImportBatch,
    ImportItem,
    Installment,
    InvestmentAccount,
    InvestmentSnapshot,
    LedgerEntry,
    Receivable,
    RecurringInstance,
    RecurringRule,
)
from .services import (
    generate_installments_for_group,
    generate_installments_from_statement,
    generate_future_installments_for_household,
    generate_recurring_instances,
    installment_plan,
    pay_recurring_instance,
    regenerate_future_installments,
    build_import_items,
)
from .utils import build_installment_logical_key
from .services_investments import (
    compute_account_series,
    compute_mom_deltas,
    compute_monthly_totals,
    get_investment_snapshots,
)

import json


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _render_partial(request, template, context, trigger=None):
    # Render do conteúdo principal
    main_html = render_to_string(template, context, request=request)

    # Render das mensagens (OOB)
    messages_html = render_to_string(
        "partials/messages.html",
        {},
        request=request,
    )

    # Junta tudo numa única resposta
    html = main_html + messages_html

    response = HttpResponse(html)

    if trigger:
        response["HX-Trigger"] = (
            json.dumps(trigger) if isinstance(trigger, dict) else trigger
        )

    return response


@login_required
def dashboard(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])

    entries = LedgerEntry.objects.filter(
        household=request.household,
        date__range=(month_start, month_end),
    )
    decimal_output = models.DecimalField(max_digits=12, decimal_places=2)
    total_income = entries.filter(kind=LedgerEntry.Kind.INCOME).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    total_expense = entries.filter(kind=LedgerEntry.Kind.EXPENSE).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    net = total_income - total_expense

    receivables_expected = Receivable.objects.filter(
        household=request.household,
        status=Receivable.Status.EXPECTED,
        expected_date__range=(month_start, month_end),
    )
    expected_total = receivables_expected.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]

    receivables_received = Receivable.objects.filter(
        household=request.household,
        status=Receivable.Status.RECEIVED,
        received_at__date__range=(month_start, month_end),
    )
    received_total = receivables_received.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]

    receivables_for_month = Receivable.objects.filter(household=request.household).filter(
        models.Q(expected_date__range=(month_start, month_end))
        | models.Q(received_at__date__range=(month_start, month_end))
    )

    entries_for_month = entries.order_by("-date", "-id")
    recurring_for_month = RecurringInstance.objects.filter(
        household=request.household, year=year, month=month
    ).select_related("rule")
    installments_for_month = Installment.objects.filter(
        household=request.household, due_date__range=(month_start, month_end)
    ).select_related("group")

    expenses_breakdown = _category_breakdown(entries.filter(kind=LedgerEntry.Kind.EXPENSE), total_expense)
    income_breakdown = _category_breakdown(entries.filter(kind=LedgerEntry.Kind.INCOME), total_income)

    line_labels, line_values = _daily_cumulative(entries.filter(kind=LedgerEntry.Kind.EXPENSE), month_start)

    expense_chart = _donut_data(expenses_breakdown)
    income_chart = _donut_data(income_breakdown)

    context = {
        "year": year,
        "month": month,
        "month_start": month_start,
        "month_end": month_end,
        "entries": entries_for_month,
        "receivables": receivables_for_month,
        "recurring_instances": recurring_for_month,
        "installments": installments_for_month,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": net,
        "expected_total": expected_total,
        "received_total": received_total,
        "expenses_breakdown": expenses_breakdown,
        "income_breakdown": income_breakdown,
        "line_chart": {"labels": line_labels, "data": line_values},
        "expense_chart": expense_chart,
        "income_chart": income_chart,
        "month_names": _month_names(),
        "year_options": _year_options(year),
    }

    if _is_htmx(request):
        return render(request, "finance/partials/_dashboard_content.html", context)
    return render(request, "finance/dashboard.html", context)


def _month_names():
    return [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ]


def _year_options(current_year):
    start = current_year - 2
    end = current_year + 2
    return list(range(start, end + 1))


def _category_breakdown(queryset, total):
    rows = (
        queryset.values("category__name")
        .annotate(
            total=Coalesce(
                Sum("amount"),
                Decimal("0.00"),
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-total")
    )
    results = []
    for row in rows:
        name = row["category__name"] or "Sem categoria"
        amount = row["total"]
        percent = (amount / total * 100) if total else 0
        results.append({"name": name, "total": amount, "percent": percent})
    return results


def _payables_context(request, year, month):
    recurring_instances = RecurringInstance.objects.filter(
        household=request.household,
        year=year,
        month=month,
    ).select_related("rule", "rule__category", "rule__account")
    installments = Installment.objects.filter(
        household=request.household,
        statement_year=year,
        statement_month=month,
    ).select_related("group", "group__card", "group__category")

    decimal_output = models.DecimalField(max_digits=12, decimal_places=2)
    recurring_total = recurring_instances.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    recurring_unpaid_total = recurring_instances.filter(is_paid=False).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    installments_total = installments.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]

    return {
        "year": year,
        "month": month,
        "recurring_instances": recurring_instances,
        "installments": installments,
        "recurring_total": recurring_total,
        "recurring_unpaid_total": recurring_unpaid_total,
        "installments_total": installments_total,
        "grand_total": recurring_total + installments_total,
    }


def _daily_cumulative(queryset, month_start):
    days_in_month = monthrange(month_start.year, month_start.month)[1]
    daily = [0] * days_in_month
    for row in queryset.values("date").annotate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0.00"),
            output_field=models.DecimalField(max_digits=12, decimal_places=2),
        )
    ):
        day_index = row["date"].day - 1
        if 0 <= day_index < days_in_month:
            daily[day_index] = float(row["total"])
    cumulative = []
    running = 0
    for value in daily:
        running += value
        cumulative.append(running)
    labels = [str(day) for day in range(1, days_in_month + 1)]
    return labels, cumulative


def _donut_data(breakdown, limit=6):
    labels = []
    data = []
    others_total = 0
    for index, item in enumerate(breakdown):
        if index < limit:
            labels.append(item["name"])
            data.append(float(item["total"]))
        else:
            others_total += float(item["total"])
    if others_total:
        labels.append("Outros")
        data.append(others_total)
    return {"labels": labels, "data": data}


@login_required
def category_list(request):
    categories = Category.objects.filter(household=request.household)
    context = {"categories": categories}
    if _is_htmx(request):
        return render(request, "finance/partials/_category_table.html", context)
    return render(request, "finance/categories_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST, household=request.household)
        if form.is_valid():
            category = form.save(commit=False)
            category.household = request.household
            category.created_by = request.user
            category.save()
            messages.success(request, "Categoria criada com sucesso.")
            categories = Category.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_category_table.html",
                {"categories": categories},
                trigger="closeModal",
            )
    else:
        form = CategoryForm(household=request.household)
    return render(request, "finance/partials/_category_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, household=request.household)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category, household=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoria atualizada.")
            categories = Category.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_category_table.html",
                {"categories": categories},
                trigger="closeModal",
            )
    else:
        form = CategoryForm(instance=category, household=request.household)
    return render(
        request,
        "finance/partials/_category_form.html",
        {"form": form, "category": category},
    )


@login_required
@require_http_methods(["POST"])
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, household=request.household)
    category.delete()
    messages.success(request, "Categoria removida.")
    categories = Category.objects.filter(household=request.household)
    return _render_partial(
        request, "finance/partials/_category_table.html", {"categories": categories}
    )


@login_required
def account_list(request):
    accounts = Account.objects.filter(household=request.household)
    context = {"accounts": accounts}
    if _is_htmx(request):
        return render(request, "finance/partials/_account_table.html", context)
    return render(request, "finance/accounts_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def account_create(request):
    if request.method == "POST":
        form = AccountForm(request.POST, household=request.household)
        if form.is_valid():
            account = form.save(commit=False)
            account.household = request.household
            account.created_by = request.user
            account.save()
            messages.success(request, "Conta criada com sucesso.")
            accounts = Account.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_account_table.html",
                {"accounts": accounts},
                trigger="closeModal",
            )
    else:
        form = AccountForm(household=request.household)
    return render(request, "finance/partials/_account_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk, household=request.household)
    if request.method == "POST":
        form = AccountForm(request.POST, instance=account, household=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, "Conta atualizada.")
            accounts = Account.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_account_table.html",
                {"accounts": accounts},
                trigger="closeModal",
            )
    else:
        form = AccountForm(instance=account, household=request.household)
    return render(
        request,
        "finance/partials/_account_form.html",
        {"form": form, "account": account},
    )


@login_required
@require_http_methods(["POST"])
def account_delete(request, pk):
    account = get_object_or_404(Account, pk=pk, household=request.household)
    account.delete()
    messages.success(request, "Conta removida.")
    accounts = Account.objects.filter(household=request.household)
    return _render_partial(
        request, "finance/partials/_account_table.html", {"accounts": accounts}
    )


@login_required
def _entry_period(request):
    today = date.today()
    year = int(request.POST.get("year", request.GET.get("year", today.year)))
    month = int(request.POST.get("month", request.GET.get("month", today.month)))
    return year, month


def entry_list(request):
    year, month = _entry_period(request)
    entries = LedgerEntry.objects.filter(
        household=request.household,
        date__year=year,
        date__month=month,
    )
    context = {"entries": entries, "year": year, "month": month}
    if _is_htmx(request):
        return render(request, "finance/partials/_entry_table.html", context)
    return render(request, "finance/entries_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def entry_create(request):
    year, month = _entry_period(request)
    if request.method == "POST":
        form = LedgerEntryForm(request.POST, household=request.household)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.household = request.household
            entry.created_by = request.user
            entry.save()
            messages.success(request, "Lançamento criado.")
            entries = LedgerEntry.objects.filter(
                household=request.household,
                date__year=year,
                date__month=month,
            )
            return _render_partial(
                request,
                "finance/partials/_entry_table.html",
                {"entries": entries, "year": year, "month": month},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = LedgerEntryForm(household=request.household)
    return render(
        request,
        "finance/partials/_entry_form.html",
        {"form": form, "year": year, "month": month},
    )


@login_required
@require_http_methods(["GET", "POST"])
def entry_edit(request, pk):
    entry = get_object_or_404(LedgerEntry, pk=pk, household=request.household)
    year, month = _entry_period(request)
    if request.method == "POST":
        form = LedgerEntryForm(request.POST, instance=entry, household=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, "Lançamento atualizado.")
            entries = LedgerEntry.objects.filter(
                household=request.household,
                date__year=year,
                date__month=month,
            )
            return _render_partial(
                request,
                "finance/partials/_entry_table.html",
                {"entries": entries, "year": year, "month": month},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = LedgerEntryForm(instance=entry, household=request.household)
    return render(
        request,
        "finance/partials/_entry_form.html",
        {"form": form, "entry": entry, "year": year, "month": month},
    )


@login_required
@require_http_methods(["POST"])
def entry_delete(request, pk):
    entry = get_object_or_404(LedgerEntry, pk=pk, household=request.household)
    year, month = _entry_period(request)
    entry.delete()
    messages.success(request, "Lançamento removido.")
    entries = LedgerEntry.objects.filter(
        household=request.household,
        date__year=year,
        date__month=month,
    )
    return _render_partial(
        request,
        "finance/partials/_entry_table.html",
        {"entries": entries, "year": year, "month": month},
        trigger={"dashboard:refresh": True},
    )


@login_required
def receivable_list(request):
    status = request.GET.get("status", "all")
    receivables = Receivable.objects.filter(household=request.household)
    if status != "all":
        receivables = receivables.filter(status=status)
    context = {"receivables": receivables, "status": status}
    if _is_htmx(request):
        return render(request, "finance/partials/_receivable_table.html", context)
    return render(request, "finance/receivables_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def receivable_create(request):
    if request.method == "POST":
        form = ReceivableForm(request.POST, household=request.household)
        if form.is_valid():
            receivable = form.save(commit=False)
            receivable.household = request.household
            receivable.created_by = request.user
            receivable.save()
            messages.success(request, "Recebível criado.")
            receivables = Receivable.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_receivable_table.html",
                {"receivables": receivables, "status": "all"},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = ReceivableForm(household=request.household)
    return render(request, "finance/partials/_receivable_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def receivable_edit(request, pk):
    receivable = get_object_or_404(Receivable, pk=pk, household=request.household)
    if request.method == "POST":
        form = ReceivableForm(request.POST, instance=receivable, household=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, "Recebível atualizado.")
            receivables = Receivable.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_receivable_table.html",
                {"receivables": receivables, "status": "all"},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = ReceivableForm(instance=receivable, household=request.household)
    return render(
        request,
        "finance/partials/_receivable_form.html",
        {"form": form, "receivable": receivable},
    )


@login_required
@require_http_methods(["POST"])
def receivable_delete(request, pk):
    status = request.POST.get("status", "all")
    receivable = get_object_or_404(Receivable, pk=pk, household=request.household)
    receivable.delete()
    messages.success(request, "Recebível removido.")
    receivables = Receivable.objects.filter(household=request.household)
    if status != "all":
        receivables = receivables.filter(status=status)
    return _render_partial(
        request,
        "finance/partials/_receivable_table.html",
        {"receivables": receivables, "status": status},
        trigger={"dashboard:refresh": True},
    )


@login_required
@require_http_methods(["POST"])
def receivable_receive(request, pk):
    status = request.POST.get("status", "all")
    receivable = get_object_or_404(Receivable, pk=pk, household=request.household)

    with transaction.atomic():
        receivable = Receivable.objects.select_for_update().get(pk=receivable.pk)
        if receivable.status != Receivable.Status.RECEIVED:
            receivable.status = Receivable.Status.RECEIVED
            receivable.received_at = timezone.now()
            if receivable.ledger_entry is None:
                entry = LedgerEntry.objects.create(
                    household=request.household,
                    date=receivable.expected_date,
                    kind=LedgerEntry.Kind.INCOME,
                    amount=receivable.amount,
                    description=receivable.description,
                    category=receivable.category,
                    account=receivable.account,
                    created_by=request.user,
                )
                receivable.ledger_entry = entry
            receivable.save()

    messages.success(request, "Recebível marcado como recebido.")
    receivables = Receivable.objects.filter(household=request.household)
    if status != "all":
        receivables = receivables.filter(status=status)
    return _render_partial(
        request,
        "finance/partials/_receivable_table.html",
        {"receivables": receivables, "status": status},
        trigger={"dashboard:refresh": True},
    )


@login_required
@require_http_methods(["POST"])
def receivable_cancel(request, pk):
    status = request.POST.get("status", "all")
    receivable = get_object_or_404(Receivable, pk=pk, household=request.household)
    if receivable.status != Receivable.Status.CANCELED:
        receivable.status = Receivable.Status.CANCELED
        receivable.save(update_fields=["status"])
    messages.success(request, "Recebível cancelado.")
    receivables = Receivable.objects.filter(household=request.household)
    if status != "all":
        receivables = receivables.filter(status=status)
    return _render_partial(
        request,
        "finance/partials/_receivable_table.html",
        {"receivables": receivables, "status": status},
        trigger={"dashboard:refresh": True},
    )


@login_required
def card_list(request):
    cards = Card.objects.filter(household=request.household)
    if _is_htmx(request):
        return render(
            request,
            "finance/partials/_card_table.html",
            {"cards": cards, "today": timezone.localdate()},
        )
    return render(
        request,
        "finance/cards_list.html",
        {"cards": cards, "today": timezone.localdate()},
    )


@login_required
@require_http_methods(["GET", "POST"])
def card_create(request):
    if request.method == "POST":
        form = CardForm(request.POST, household=request.household)
        if form.is_valid():
            card = form.save(commit=False)
            card.household = request.household
            card.created_by = request.user
            card.save()
            messages.success(request, "Cartão criado.")
            cards = Card.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_card_table.html",
                {"cards": cards, "today": timezone.localdate()},
                trigger={"closeModal": True},
            )
    else:
        form = CardForm(household=request.household)
    return render(request, "finance/partials/_card_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def card_edit(request, pk):
    card = get_object_or_404(Card, pk=pk, household=request.household)
    if request.method == "POST":
        form = CardForm(request.POST, instance=card, household=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, "Cartão atualizado.")
            cards = Card.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_card_table.html",
                {"cards": cards, "today": timezone.localdate()},
                trigger={"closeModal": True},
            )
    else:
        form = CardForm(instance=card, household=request.household)
    return render(request, "finance/partials/_card_form.html", {"form": form, "card": card})


@login_required
@require_http_methods(["POST"])
def card_delete(request, pk):
    card = get_object_or_404(Card, pk=pk, household=request.household)
    card.delete()
    messages.success(request, "Cartão removido.")
    cards = Card.objects.filter(household=request.household)
    return _render_partial(
        request,
        "finance/partials/_card_table.html",
        {"cards": cards, "today": timezone.localdate()},
    )


@login_required
def card_statement(request, pk, year, month):
    card = get_object_or_404(Card, pk=pk, household=request.household)
    if "year" in request.GET or "month" in request.GET:
        redirect_year = int(request.GET.get("year", year))
        redirect_month = int(request.GET.get("month", month))
        return redirect("finance:card-statement", pk=card.pk, year=redirect_year, month=redirect_month)
    closing_date, period_start, period_end = get_statement_window(year, month, card.closing_day)
    due_date = get_due_date(year, month, card.due_day)
    month_label = _month_names()[month - 1]
    installments = Installment.objects.filter(
        household=request.household,
        group__card=card,
    ).filter(
        models.Q(statement_year=year, statement_month=month)
        | models.Q(statement_year__isnull=True, due_date__year=year, due_date__month=month)
    ).select_related("group")
    decimal_output = models.DecimalField(max_digits=12, decimal_places=2)
    total = installments.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    by_category = (
        installments.values("group__category__name")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output))
        .order_by("-total")
    )
    context = {
        "card": card,
        "statement_year": year,
        "statement_month": month,
        "statement_month_label": month_label,
        "closing_date": closing_date,
        "due_date": due_date,
        "period_start": period_start,
        "period_end": period_end,
        "installments": installments.order_by("number"),
        "statement_total": total,
        "category_breakdown": by_category,
        "month_names": _month_names(),
        "year_options": _year_options(year),
    }
    return render(request, "finance/card_statement.html", context)


@login_required
def purchase_list(request):
    groups = CardPurchaseGroup.objects.filter(household=request.household).select_related("card")
    return render(request, "finance/purchases_list.html", {"groups": groups})


@login_required
@require_http_methods(["GET", "POST"])
def purchase_create(request):
    if request.method == "POST":
        form = CardPurchaseGroupForm(request.POST, household=request.household)
        if form.is_valid():
            group = form.save(commit=False)
            group.household = request.household
            group.created_by = request.user
            group.save()
            generate_installments_for_group(group)
            messages.success(request, "Compra parcelada criada.")
            groups = CardPurchaseGroup.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_purchase_table.html",
                {"groups": groups},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = CardPurchaseGroupForm(household=request.household)
    return render(request, "finance/partials/_purchase_form.html", {"form": form})


@login_required
def purchase_detail(request, pk):
    group = get_object_or_404(CardPurchaseGroup, pk=pk, household=request.household)
    installments = group.installments.order_by("number")
    return render(
        request,
        "finance/purchase_detail.html",
        {"group": group, "installments": installments},
    )


@login_required
@require_http_methods(["POST"])
def purchase_delete(request, pk):
    group = get_object_or_404(CardPurchaseGroup, pk=pk, household=request.household)
    group.delete()
    messages.success(request, "Compra removida.")
    groups = CardPurchaseGroup.objects.filter(household=request.household)
    return _render_partial(
        request,
        "finance/partials/_purchase_table.html",
        {"groups": groups},
        trigger={"dashboard:refresh": True},
    )


@login_required
@require_http_methods(["POST"])
def purchase_regenerate(request, pk):
    group = get_object_or_404(CardPurchaseGroup, pk=pk, household=request.household)
    from_date = request.POST.get("from_date")
    from_date = date.fromisoformat(from_date) if from_date else timezone.localdate()
    regenerate_future_installments(group, from_date)
    messages.success(request, "Parcelas futuras recriadas.")
    return redirect("finance:purchase-detail", pk=group.pk)


@login_required
def payables_list(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    context = _payables_context(request, year, month)
    context.update(
        {
            "month_names": _month_names(),
            "year_options": _year_options(year),
        }
    )
    if _is_htmx(request):
        return _render_partial(request, "finance/partials/_payables_content.html", context)
    return render(request, "finance/payables.html", context)


@login_required
@require_http_methods(["POST"])
def payables_generate(request):
    months_ahead = int(request.POST.get("months_ahead", 6) or 6)
    today = timezone.localdate()
    year = int(request.POST.get("year", today.year))
    month = int(request.POST.get("month", today.month))

    print("\n[PAYABLES_GENERATE]")
    print("months_ahead:", months_ahead)
    print("filter year/month:", year, month)
    print("household:", request.household.id)

    rules = RecurringRule.objects.filter(household=request.household, active=True)
    print("active rules found:", rules.count())

    created_count = 0

    for rule in rules:
        print(f"\n[PAYABLES_GENERATE] rule {rule.id} - {rule.description}")
        created = generate_recurring_instances(rule, months_ahead)
        print(f"instances created for rule {rule.id}: {len(created)}")
        created_count += len(created)

    total_created = created_count
    print("[PAYABLES_GENERATE] TOTAL CREATED:", total_created)
    messages.success(
        request,
        f"{total_created} instância(s) gerada(s).",
    )

    context = _payables_context(request, year, month)
    return _render_partial(
        request,
        "finance/partials/_payables_content.html",
        context,
    )



@login_required
@require_http_methods(["POST"])
def payables_recurring_pay(request, pk):
    instance = get_object_or_404(RecurringInstance, pk=pk, household=request.household)
    instance = pay_recurring_instance(instance)
    messages.success(request, "Recorrência paga.")
    return _render_partial(
        request,
        "finance/partials/_payables_recurring_row.html",
        {"instance": instance},
        trigger={"dashboard:refresh": True, "payables:refresh": True},
    )


@login_required
def recurring_list(request):
    rules = RecurringRule.objects.filter(household=request.household)
    return render(request, "finance/recurring_list.html", {"rules": rules})


@login_required
@require_http_methods(["GET", "POST"])
def recurring_create(request):
    months_ahead = int(request.POST.get("months_ahead", 3) or 3)
    if request.method == "POST":
        form = RecurringRuleForm(request.POST, household=request.household)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.household = request.household
            rule.created_by = request.user
            rule.save()
            generate_recurring_instances(rule, months_ahead)
            messages.success(request, "Recorrência criada.")
            rules = RecurringRule.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_recurring_table.html",
                {"rules": rules},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = RecurringRuleForm(household=request.household)
    return render(
        request,
        "finance/partials/_recurring_form.html",
        {"form": form, "months_ahead": months_ahead},
    )


@login_required
@require_http_methods(["GET", "POST"])
def recurring_edit(request, pk):
    rule = get_object_or_404(RecurringRule, pk=pk, household=request.household)
    if request.method == "POST":
        form = RecurringRuleForm(request.POST, instance=rule, household=request.household)
        if form.is_valid():
            form.save()
            messages.success(request, "Recorrência atualizada.")
            rules = RecurringRule.objects.filter(household=request.household)
            return _render_partial(
                request,
                "finance/partials/_recurring_table.html",
                {"rules": rules},
                trigger={"closeModal": True},
            )
    else:
        form = RecurringRuleForm(instance=rule, household=request.household)
    return render(request, "finance/partials/_recurring_form.html", {"form": form, "rule": rule})


@login_required
@require_http_methods(["POST"])
def recurring_delete(request, pk):
    rule = get_object_or_404(RecurringRule, pk=pk, household=request.household)
    rule.delete()
    messages.success(request, "Recorrência removida.")
    rules = RecurringRule.objects.filter(household=request.household)
    return _render_partial(request, "finance/partials/_recurring_table.html", {"rules": rules})


@login_required
@require_http_methods(["POST"])
def recurring_generate(request, pk):
    rule = get_object_or_404(RecurringRule, pk=pk, household=request.household)
    months_ahead = int(request.POST.get("months_ahead", 3) or 3)
    generate_recurring_instances(rule, months_ahead)
    messages.success(request, "Instâncias geradas.")
    rules = RecurringRule.objects.filter(household=request.household)
    return _render_partial(request, "finance/partials/_recurring_table.html", {"rules": rules})


@login_required
def recurring_instances(request):
    year = int(request.GET.get("year"))
    month = int(request.GET.get("month"))
    instances = RecurringInstance.objects.filter(
        household=request.household, year=year, month=month
    ).select_related("rule")
    return render(
        request,
        "finance/partials/_recurring_instances_table.html",
        {"instances": instances, "year": year, "month": month},
    )


@login_required
@require_http_methods(["POST"])
def recurring_instance_pay(request, pk):
    instance = get_object_or_404(RecurringInstance, pk=pk, household=request.household)
    instance = pay_recurring_instance(instance)
    messages.success(request, "Recorrência paga.")
    return _render_partial(
        request,
        "finance/partials/_recurring_instances_row.html",
        {"instance": instance},
        trigger={"dashboard:refresh": True},
    )


@login_required
@require_http_methods(["GET", "POST"])
def recurring_instance_value(request, pk):
    instance = get_object_or_404(RecurringInstance, pk=pk, household=request.household)
    if instance.is_paid:
        messages.error(request, "Não é possível alterar uma recorrência já paga.")
        return _render_partial(
            request,
            "finance/partials/_recurring_instances_row.html",
            {"instance": instance},
        )
    if request.method == "POST":
        form = RecurringInstanceValueOverrideForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Valor atualizado.")
            return _render_partial(
                request,
                "finance/partials/_recurring_instances_row.html",
                {"instance": instance},
                trigger={"closeModal": True, "dashboard:refresh": True},
            )
    else:
        form = RecurringInstanceValueOverrideForm(instance=instance)
    return render(
        request,
        "finance/partials/_recurring_instance_value_form.html",
        {"form": form, "instance": instance},
    )

@login_required
def import_start(request):
    today = timezone.localdate()

    print("\n[IMPORT_START]")
    print("[IMPORT_START] today:", today)
    print("[IMPORT_START] household:", request.household.id)
    print("[IMPORT_START] user:", request.user.id)

    form = ImportPasteForm(
        household=request.household,
        initial={
            "statement_year": today.year,
            "statement_month": today.month,
        },
    )
    return render(request, "finance/import_start.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def import_parse(request):
    print("\n[IMPORT_PARSE] ===============================")
    print("[IMPORT_PARSE] POST recebido")
    print("[IMPORT_PARSE] household:", request.household.id)
    print("[IMPORT_PARSE] user:", request.user.id)

    form = ImportPasteForm(request.POST, household=request.household)
    if not form.is_valid():
        print("[IMPORT_PARSE] FORM INVÁLIDO")
        print("[IMPORT_PARSE] erros:", form.errors)
        return render(request, "finance/import_start.html", {"form": form})

    source_text = form.cleaned_data["source_text"]
    card = form.cleaned_data.get("card")
    statement_year = form.cleaned_data["statement_year"]
    statement_month = form.cleaned_data["statement_month"]

    print("[IMPORT_PARSE] statement_year:", statement_year)
    print("[IMPORT_PARSE] statement_month:", statement_month)
    print("[IMPORT_PARSE] card:", card.id if card else None)
    print("[IMPORT_PARSE] closing_day:", card.closing_day if card else None)

    print("\n[IMPORT_PARSE] ===== SOURCE TEXT =====")
    print(source_text)
    print("[IMPORT_PARSE] ===== END SOURCE TEXT =====\n")

    if card is None:
        messages.error(request, "Selecione um cartão para importar.")
        return render(request, "finance/import_start.html", {"form": form})

    parsed_items = parse_statement_text(
        source_text,
        statement_year=statement_year,
        statement_month=statement_month,
        closing_day=card.closing_day,
    )

    print(f"[PARSE] itens parseados: {len(parsed_items)}")

    for i, item in enumerate(parsed_items[:10]):
        print(
            "[PARSE ITEM]",
            {
                "purchase_date": item.purchase_date,
                "statement_year": item.statement_year,
                "statement_month": item.statement_month,
                "description": item.description,
                "amount": item.amount,
                "installments_current": item.installments_current,
                "installments_total": item.installments_total,
                "flag": item.flag,
                "prefix_raw": item.prefix_raw,
            },
        )

    if not parsed_items:
        messages.error(request, "Nenhum item válido encontrado.")
        return render(request, "finance/import_start.html", {"form": form})

    batch = ImportBatch.objects.create(
        household=request.household,
        created_by=request.user,
        source_text=source_text,
        card=card,
        statement_year=statement_year,
        statement_month=statement_month,
    )

    print("[IMPORT_PARSE] batch criado:", batch.id)

    items_payload = []
    for item in parsed_items:
        payload = {
            "purchase_date": item.purchase_date,
            "statement_year": item.statement_year,
            "statement_month": item.statement_month,
            "description": item.description,
            "amount": item.amount,
            "installments_total": item.installments_total,
            "installments_current": item.installments_current,
            "purchase_flag": item.flag,
            "purchase_prefix_raw": item.prefix_raw or "",
            "purchase_type_raw": "",
        }
        print("[IMPORT_PAYLOAD_ITEM]", payload)
        items_payload.append(payload)

    build_import_items(batch, items_payload)

    return redirect("finance:import-review", batch.pk)


@login_required
def import_review(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk, household=request.household)

    print("\n[IMPORT_REVIEW]")
    print("[IMPORT_REVIEW] batch:", batch.id)
    print("[IMPORT_REVIEW] status:", batch.status)
    print("[IMPORT_REVIEW] card:", batch.card_id)
    print("[IMPORT_REVIEW] statement:", batch.statement_month, batch.statement_year)
    print("[IMPORT_REVIEW] items:", batch.items.count())

    items = list(batch.items.all())
    logical_keys = [
        build_installment_logical_key(
            item.description,
            item.purchase_date,
            item.amount,
            item.installments_total,
        )
        for item in items
    ]
    existing_groups = CardPurchaseGroup.objects.filter(
        household=request.household,
        logical_key__in=logical_keys,
    )
    if batch.card:
        existing_groups = existing_groups.filter(card=batch.card)

    existing_logical_keys = set(
        existing_groups.values_list("logical_key", flat=True)
    )
    seen_logical_keys: set[str] = set()
    item_statuses: dict[int, str] = {}

    for item, logical_key in zip(items, logical_keys):
        if logical_key in existing_logical_keys:
            status = "EXISTING_IN_DB"
        elif logical_key in seen_logical_keys:
            status = "DUPLICATE_IN_FILE"
        else:
            status = "NEW"
        seen_logical_keys.add(logical_key)
        item_statuses[item.id] = status

    formset = ImportReviewFormSet(
        queryset=items,
        form_kwargs={"household": request.household},
    )
    for form in formset:
        form.dedup_status = item_statuses.get(form.instance.id, "NEW")

    card_form = ImportPasteForm(
        household=request.household,
        initial={
            "card": batch.card,
            "statement_year": batch.statement_year,
            "statement_month": batch.statement_month,
        },
    )

    return render(
        request,
        "finance/import_review.html",
        {
            "batch": batch,
            "formset": formset,
            "card_form": card_form,
        },
    )


@login_required
@require_http_methods(["POST"])
def import_confirm(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk, household=request.household)

    print("\n[IMPORT_CONFIRM] ===============================")
    print("[IMPORT_CONFIRM] batch:", batch.id)
    print("[IMPORT_CONFIRM] status:", batch.status)

    if batch.status == ImportBatch.Status.CONFIRMED:
        messages.info(request, "Importação já confirmada.")
        return redirect("dashboard")

    formset = ImportReviewFormSet(
        request.POST,
        queryset=batch.items.all(),
        form_kwargs={"household": request.household},
    )
    selected_ids_raw = request.POST.getlist("selected_items")
    selected_ids = {int(item_id) for item_id in selected_ids_raw if item_id}

    card_id = request.POST.get("card")
    if card_id:
        batch.card = Card.objects.filter(
            household=request.household, id=card_id
        ).first()
        batch.save(update_fields=["card"])

    statement_year_raw = request.POST.get("statement_year") or batch.statement_year
    statement_month_raw = request.POST.get("statement_month") or batch.statement_month

    print("[IMPORT_CONFIRM] statement_year_raw:", statement_year_raw)
    print("[IMPORT_CONFIRM] statement_month_raw:", statement_month_raw)

    if not statement_year_raw or not statement_month_raw:
        messages.error(request, "Informe o ano e mês da fatura.")
        return render(
            request,
            "finance/import_review.html",
            {"batch": batch, "formset": formset},
        )

    statement_year = int(statement_year_raw)
    statement_month = int(statement_month_raw)

    print("[IMPORT_CONFIRM] statement_year:", statement_year)
    print("[IMPORT_CONFIRM] statement_month:", statement_month)
    print("[IMPORT_CONFIRM] card:", batch.card.id if batch.card else None)
    print("[IMPORT_CONFIRM] closing_day:", batch.card.closing_day if batch.card else None)

    if batch.statement_year != statement_year or batch.statement_month != statement_month:
        batch.statement_year = statement_year
        batch.statement_month = statement_month
        batch.save(update_fields=["statement_year", "statement_month"])

    if not formset.is_valid():
        print("[IMPORT_CONFIRM] FORMSET INVÁLIDO")
        print(formset.errors)
        messages.error(request, "Corrija os itens antes de confirmar.")
        return render(
            request,
            "finance/import_review.html",
            {"batch": batch, "formset": formset},
        )

    with transaction.atomic():
        print("[IMPORT_CONFIRM] INÍCIO TRANSACTION")

        created_installments_count = 0

        for idx, form in enumerate(formset):
            print(f"\n[IMPORT_CONFIRM] LOOP IDX = {idx}")

            item = form.save(commit=False)
            item.batch = batch
            item.statement_year = statement_year
            item.statement_month = statement_month
            item.save()

            print("[IMPORT_CONFIRM] item salvo:", item.id)

            if item.removed or item.id not in selected_ids:
                print("[IMPORT_CONFIRM] item removido:", item.id)
                continue

            print("\n[IMPORT_CONFIRM][ITEM]")
            print("id:", item.id)
            print("description:", item.description)
            print("purchase_date:", item.purchase_date)
            print("parcela_amount:", item.amount)
            print(
                "installments:",
                f"{item.installments_current}/{item.installments_total}",
            )
            print("category:", item.category_id)

            closing_date, window_start, window_end = get_statement_window(
                statement_year,
                statement_month,
                batch.card.closing_day,
            )

            print("[STATEMENT WINDOW]")
            print("window_start:", window_start)
            print("window_end:", window_end)
            print("closing_date:", closing_date)

            total_amount = item.amount * item.installments_total

            print("[IMPORT_CONFIRM] total_amount calculado:", total_amount)

            group = None
            logical_key = None
            if item.installments_total and item.installments_total > 1:
                # Deterministic match only; descrição variável pode exigir normalização extra em sprint futura.
                logical_key = build_installment_logical_key(
                    item.description,
                    item.purchase_date,
                    item.amount,
                    item.installments_total,
                )
                group = CardPurchaseGroup.objects.filter(
                    household=request.household,
                    card=batch.card,
                    logical_key=logical_key,
                ).first()

            if group is None:
                group = CardPurchaseGroup.objects.create(
                    household=request.household,
                    card=batch.card,
                    description=item.description,
                    logical_key=logical_key,
                    total_amount=total_amount,
                    installments_count=item.installments_total,
                    first_due_date=closing_date,
                    purchase_date=item.purchase_date,
                    statement_year=statement_year,
                    statement_month=statement_month,
                    category=item.category,
                    created_by=request.user,
                )

            print("[IMPORT_CONFIRM] group criado:", group.id)

            current_installment = item.installments_current or 1

            print(
                "[IMPORT_CONFIRM] antes generate_installments_from_statement | current:",
                current_installment,
            )

            created_installments = generate_installments_from_statement(
                group,
                statement_year=statement_year,
                statement_month=statement_month,
                current_installment=current_installment,
            )

            print("[IMPORT_CONFIRM] depois generate_installments_from_statement")
            created_installments_count += len(created_installments)

        print("[IMPORT_CONFIRM] FIM LOOP")

        batch.status = ImportBatch.Status.CONFIRMED
        batch.confirmed_at = timezone.now()
        batch.save(update_fields=["status", "confirmed_at"])

        print("[IMPORT_CONFIRM] batch confirmado:", batch.id)

    print("[IMPORT_CONFIRM] FIM TRANSACTION")

    messages.success(
        request,
        f"Importação confirmada. {created_installments_count} parcela(s) nova(s).",
    )
    return redirect("dashboard")



def _investment_summary_context(request, year):
    snapshots = list(get_investment_snapshots(request.household, year))
    accounts = InvestmentAccount.objects.filter(household=request.household).order_by("name")
    month_names = _month_names()
    monthly_totals = compute_monthly_totals(snapshots)
    deltas = compute_mom_deltas(monthly_totals)
    account_series = compute_account_series(snapshots)

    account_trends = []
    for account in accounts:
        series = account_series.get(account.id, [Decimal("0.00") for _ in range(12)])
        account_trends.append(
            {
                "label": account.name,
                "data": [float(value) for value in series],
            }
        )

    account_rows = []
    snapshots_by_account = {}
    for snapshot in snapshots:
        snapshots_by_account.setdefault(snapshot.account_id, []).append(snapshot)
    for account in accounts:
        account_snapshots = sorted(snapshots_by_account.get(account.id, []), key=lambda item: item.month)
        previous_balance = None
        for snapshot in account_snapshots:
            if previous_balance is None:
                delta_abs = None
                delta_pct = None
            else:
                delta_abs = snapshot.balance - previous_balance
                if previous_balance == 0 and snapshot.balance == 0:
                    delta_pct = Decimal("0.00")
                elif previous_balance == 0 and snapshot.balance != 0:
                    delta_pct = None
                else:
                    delta_pct = (delta_abs / previous_balance) * Decimal("100.00")
            account_rows.append(
                {
                    "account": account,
                    "snapshot": snapshot,
                    "delta_abs": delta_abs,
                    "delta_pct": delta_pct,
                }
            )
            previous_balance = snapshot.balance

    monthly_rows = []
    for delta in deltas:
        monthly_rows.append(
            {
                "month": delta.month,
                "month_name": month_names[delta.month - 1],
                "total": delta.total,
                "delta_abs": delta.delta_abs,
                "delta_pct": delta.delta_pct,
            }
        )

    context = {
        "year": year,
        "month_names": month_names,
        "monthly_totals": monthly_totals,
        "monthly_deltas": deltas,
        "monthly_rows": monthly_rows,
        "account_rows": account_rows,
        "total_chart": {
            "labels": month_names,
            "data": [float(total) for total in monthly_totals],
        },
        "delta_chart": {
            "labels": month_names,
            "data": [
                float(delta.delta_pct) if delta.delta_pct is not None else None for delta in deltas
            ],
        },
        "account_chart": {
            "labels": month_names,
            "datasets": account_trends,
        },
    }
    return context


@login_required
def investments_list(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    current_year = today.year
    current_month = today.month
    previous_month = 12 if current_month == 1 else current_month - 1
    previous_year = current_year - 1 if current_month == 1 else current_year

    accounts = InvestmentAccount.objects.filter(household=request.household).order_by("name")
    account_overview = []
    for account in accounts:
        current_snapshot = InvestmentSnapshot.objects.filter(
            household=request.household,
            account=account,
            year=current_year,
            month=current_month,
        ).first()
        previous_snapshot = InvestmentSnapshot.objects.filter(
            household=request.household,
            account=account,
            year=previous_year,
            month=previous_month,
        ).first()
        delta_abs = None
        delta_pct = None
        if current_snapshot and previous_snapshot:
            delta_abs = current_snapshot.balance - previous_snapshot.balance
            if previous_snapshot.balance == 0 and current_snapshot.balance == 0:
                delta_pct = Decimal("0.00")
            elif previous_snapshot.balance == 0 and current_snapshot.balance != 0:
                delta_pct = None
            else:
                delta_pct = (delta_abs / previous_snapshot.balance) * Decimal("100.00")
        account_overview.append(
            {
                "account": account,
                "current_snapshot": current_snapshot,
                "previous_snapshot": previous_snapshot,
                "delta_abs": delta_abs,
                "delta_pct": delta_pct,
            }
        )

    summary_context = _investment_summary_context(request, year)
    context = {
        "accounts": accounts,
        "account_overview": account_overview,
        "year": year,
        "year_options": _year_options(year),
        **summary_context,
    }
    return render(request, "finance/investments_list.html", context)


@login_required
def investments_summary(request):
    year = int(request.GET.get("year"))
    context = _investment_summary_context(request, year)
    return render(request, "finance/partials/_investments_summary.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def investment_account_create(request):
    if request.method == "POST":
        form = InvestmentAccountForm(request.POST, household=request.household)
        if form.is_valid():
            account = form.save(commit=False)
            account.household = request.household
            account.created_by = request.user
            account.save()
            accounts = InvestmentAccount.objects.filter(household=request.household).order_by("name")
            return _render_partial(
                request,
                "finance/partials/_investment_account_table.html",
                {"accounts": accounts},
                trigger={"closeModal": True, "investments:refresh": True},
            )
    else:
        form = InvestmentAccountForm(household=request.household)
    return render(request, "finance/partials/_investment_account_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def investment_account_edit(request, pk):
    account = get_object_or_404(InvestmentAccount, pk=pk, household=request.household)
    if request.method == "POST":
        form = InvestmentAccountForm(request.POST, instance=account, household=request.household)
        if form.is_valid():
            form.save()
            accounts = InvestmentAccount.objects.filter(household=request.household).order_by("name")
            return _render_partial(
                request,
                "finance/partials/_investment_account_table.html",
                {"accounts": accounts},
                trigger={"closeModal": True, "investments:refresh": True},
            )
    else:
        form = InvestmentAccountForm(instance=account, household=request.household)
    return render(
        request,
        "finance/partials/_investment_account_form.html",
        {"form": form, "account": account},
    )


@login_required
@require_http_methods(["POST"])
def investment_account_delete(request, pk):
    account = get_object_or_404(InvestmentAccount, pk=pk, household=request.household)
    account.delete()
    accounts = InvestmentAccount.objects.filter(household=request.household).order_by("name")
    return _render_partial(
        request,
        "finance/partials/_investment_account_table.html",
        {"accounts": accounts},
        trigger={"investments:refresh": True},
    )


@login_required
@require_http_methods(["GET", "POST"])
def investment_snapshot_create(request):
    initial = {}
    if "account_id" in request.GET:
        initial["account"] = get_object_or_404(
            InvestmentAccount, pk=request.GET.get("account_id"), household=request.household
        )
    if "year" in request.GET:
        initial["year"] = int(request.GET.get("year"))
    if "month" in request.GET:
        initial["month"] = int(request.GET.get("month"))
    summary_year = request.GET.get("year") or timezone.localdate().year

    if request.method == "POST":
        form = InvestmentSnapshotForm(request.POST, household=request.household)
        if form.is_valid():
            snapshot = form.save(commit=False)
            snapshot.household = request.household
            snapshot.created_by = request.user
            snapshot.save()
            return _render_partial(
                request,
                "finance/partials/_investments_summary.html",
                _investment_summary_context(request, int(request.POST.get("summary_year", summary_year))),
                trigger={"closeModal": True},
            )
    else:
        form = InvestmentSnapshotForm(initial=initial, household=request.household)
    return render(
        request,
        "finance/partials/_investment_snapshot_form.html",
        {"form": form, "summary_year": summary_year},
    )


@login_required
@require_http_methods(["GET", "POST"])
def investment_snapshot_edit(request, pk):
    snapshot = get_object_or_404(InvestmentSnapshot, pk=pk, household=request.household)
    summary_year = request.GET.get("year") or snapshot.year
    if request.method == "POST":
        form = InvestmentSnapshotForm(request.POST, instance=snapshot, household=request.household)
        if form.is_valid():
            form.save()
            return _render_partial(
                request,
                "finance/partials/_investments_summary.html",
                _investment_summary_context(request, int(request.POST.get("summary_year", summary_year))),
                trigger={"closeModal": True},
            )
    else:
        form = InvestmentSnapshotForm(instance=snapshot, household=request.household)
    return render(
        request,
        "finance/partials/_investment_snapshot_form.html",
        {"form": form, "summary_year": summary_year, "snapshot": snapshot},
    )


@login_required
@require_http_methods(["POST"])
def investment_snapshot_delete(request, pk):
    snapshot = get_object_or_404(InvestmentSnapshot, pk=pk, household=request.household)
    summary_year = request.POST.get("summary_year", snapshot.year)
    snapshot.delete()
    return _render_partial(
        request,
        "finance/partials/_investments_summary.html",
        _investment_summary_context(request, int(summary_year)),
    )


def _annual_stats_context(request, year):
    entries = LedgerEntry.objects.filter(household=request.household, date__year=year)
    decimal_output = models.DecimalField(max_digits=12, decimal_places=2)
    income_total = entries.filter(kind=LedgerEntry.Kind.INCOME).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    expense_total = entries.filter(kind=LedgerEntry.Kind.EXPENSE).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output)
    )["total"]
    net_total = income_total - expense_total

    income_by_category = list(
        entries.filter(kind=LedgerEntry.Kind.INCOME)
        .values("category__name")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output))
        .order_by("-total")
    )
    expense_by_category = list(
        entries.filter(kind=LedgerEntry.Kind.EXPENSE)
        .values("category__name")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output))
        .order_by("-total")
    )
    income_by_account = list(
        entries.filter(kind=LedgerEntry.Kind.INCOME)
        .values("account__name")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output))
        .order_by("-total")
    )
    expense_by_account = list(
        entries.filter(kind=LedgerEntry.Kind.EXPENSE)
        .values("account__name")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output))
        .order_by("-total")
    )
    purchase_groups = list(
        Installment.objects.filter(household=request.household, due_date__year=year)
        .values("group__description")
        .annotate(total=Coalesce(Sum("amount"), Decimal("0.00"), output_field=decimal_output))
        .order_by("-total")
    )

    snapshots = list(get_investment_snapshots(request.household, year))
    month_names = _month_names()
    monthly_totals = compute_monthly_totals(snapshots)
    monthly_deltas = compute_mom_deltas(monthly_totals)
    investment_monthly_rows = [
        {
            "month": delta.month,
            "month_name": month_names[delta.month - 1],
            "total": delta.total,
            "delta_abs": delta.delta_abs,
            "delta_pct": delta.delta_pct,
        }
        for delta in monthly_deltas
    ]
    months_with_data = {snapshot.month for snapshot in snapshots}
    if months_with_data:
        start_month = min(months_with_data)
        end_month = max(months_with_data)
        start_total = monthly_totals[start_month - 1]
        end_total = monthly_totals[end_month - 1]
        delta_abs = end_total - start_total
        if start_total == 0 and end_total == 0:
            delta_pct = Decimal("0.00")
        elif start_total == 0 and end_total != 0:
            delta_pct = None
        else:
            delta_pct = (delta_abs / start_total) * Decimal("100.00")
    else:
        start_month = None
        end_month = None
        start_total = None
        end_total = None
        delta_abs = None
        delta_pct = None
    start_month_label = month_names[start_month - 1] if start_month else None
    end_month_label = month_names[end_month - 1] if end_month else None

    context = {
        "year": year,
        "income_total": income_total,
        "expense_total": expense_total,
        "net_total": net_total,
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category,
        "income_by_account": income_by_account,
        "expense_by_account": expense_by_account,
        "purchase_groups": purchase_groups,
        "investment_start_month": start_month,
        "investment_end_month": end_month,
        "investment_start_month_label": start_month_label,
        "investment_end_month_label": end_month_label,
        "investment_start_total": start_total,
        "investment_end_total": end_total,
        "investment_delta_abs": delta_abs,
        "investment_delta_pct": delta_pct,
        "investment_monthly_totals": monthly_totals,
        "investment_monthly_deltas": monthly_deltas,
        "investment_monthly_rows": investment_monthly_rows,
        "expense_chart": {
            "labels": [row["category__name"] or "Sem categoria" for row in expense_by_category],
            "data": [float(row["total"]) for row in expense_by_category],
        },
        "income_chart": {
            "labels": [row["category__name"] or "Sem categoria" for row in income_by_category],
            "data": [float(row["total"]) for row in income_by_category],
        },
        "investment_chart": {
            "labels": month_names,
            "data": [float(total) for total in monthly_totals],
        },
        "investment_delta_chart": {
            "labels": month_names,
            "data": [
                float(delta.delta_pct) if delta.delta_pct is not None else None
                for delta in monthly_deltas
            ],
        },
        "month_names": month_names,
    }
    return context


@login_required
def annual_stats(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    summary_context = _annual_stats_context(request, year)
    context = {
        "year": year,
        "year_options": _year_options(year),
        **summary_context,
    }
    return render(request, "finance/annual_stats.html", context)


@login_required
def annual_stats_summary(request):
    year = int(request.GET.get("year"))
    context = _annual_stats_context(request, year)
    return render(request, "finance/partials/_annual_stats_summary.html", context)
