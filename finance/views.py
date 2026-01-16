from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import AccountForm, CategoryForm, LedgerEntryForm, ReceivableForm
from .models import Account, Category, LedgerEntry, Receivable


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _render_partial(request, template, context, trigger=None):
    response = render(request, template, context)
    if trigger:
        response["HX-Trigger"] = trigger
    return response


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
                trigger="closeModal",
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
                trigger="closeModal",
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
                trigger="closeModal",
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
                trigger="closeModal",
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
        request, "finance/partials/_receivable_table.html", {"receivables": receivables, "status": status}
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
        request, "finance/partials/_receivable_table.html", {"receivables": receivables, "status": status}
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
        request, "finance/partials/_receivable_table.html", {"receivables": receivables, "status": status}
    )
