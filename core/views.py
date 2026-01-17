from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from .utils_webhook import FinanceBot
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from twilio.twiml.messaging_response import MessagingResponse


logger = logging.getLogger(__name__)
from .models import (
    HouseholdMembership,
    SystemLog,
)

logger = logging.getLogger(__name__)

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
def household_missing_view(request):
    return render(request, "core/household_missing.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


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



def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _can_manage_logs(request):
    if request.user.is_superuser:
        return True
    if request.household is None:
        return False
    return HouseholdMembership.objects.filter(
        user=request.user, household=request.household, is_primary=True
    ).exists()


def _system_logs_context():
    logs = SystemLog.objects.order_by("-created_at")
    return {"logs": logs}


@login_required
def system_logs_view(request):
    if not _can_manage_logs(request):
        return HttpResponseForbidden("Acesso negado.")
    return render(request, "core/system_logs.html", _system_logs_context())


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
    if not _can_manage_logs(request):
        return JsonResponse({"error": "Acesso negado."}, status=403)
    logs = SystemLog.objects.order_by("-created_at")
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
    if not _can_manage_logs(request):
        return JsonResponse({"error": "Acesso negado."}, status=403)
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
    if not _can_manage_logs(request):
        return JsonResponse({"pending": 0})
    count = SystemLog.objects.filter(is_resolved=False).count()
    return JsonResponse({"pending": count})


@login_required
@require_http_methods(["POST"])
def system_log_resolve(request, log_id):
    if not _can_manage_logs(request):
        return JsonResponse({"error": "Acesso negado."}, status=403)
    log = get_object_or_404(SystemLog, pk=log_id)
    log.is_resolved = True
    log.save(update_fields=["is_resolved"])
    response = render(request, "core/partials/_system_logs_table.html", _system_logs_context())
    response["HX-Trigger"] = "logs:refresh"
    return response


@login_required
@require_http_methods(["POST"])
def system_log_delete(request, log_id):
    if not _can_manage_logs(request):
        return JsonResponse({"error": "Acesso negado."}, status=403)
    log = get_object_or_404(SystemLog, pk=log_id)
    log.delete()
    response = render(request, "core/partials/_system_logs_table.html", _system_logs_context())
    response["HX-Trigger"] = "logs:refresh"
    return response


@csrf_exempt
@require_POST
def twilio_webhook(request):
    # 1. Dados básicos
    incoming_msg = request.POST.get('Body', '').strip()
    sender = request.POST.get('From')

    # 2. Identificação do Utilizador
    # (Mantendo a sua lógica atual de pegar o primeiro user)
    # Idealmente, no futuro, você pode vincular o 'sender' ao perfil do user.
    user = User.objects.first()

    # 3. Processamento via Bot
    bot = FinanceBot(sender, user)
    response_text = bot.process_message(incoming_msg)

    # 4. Resposta Twilio
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(response_text)

    return HttpResponse(str(resp))
