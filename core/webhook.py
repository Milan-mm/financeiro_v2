# core/webhook.py
import logging
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.contrib.auth.models import User
from twilio.twiml.messaging_response import MessagingResponse
from django.core.cache import cache

from core.utils_webhook import FinanceBot

logger = logging.getLogger(__name__)

# Helper para criar uma chave de cache única para cada remetente
def get_user_state_key(sender):
    return f"twilio_user_state_{sender}"

@csrf_exempt
@require_POST
def twilio_webhook(request):
    incoming_msg = request.POST.get("Body", "").strip()
    sender = request.POST.get("From", "")  # Ex: 'whatsapp:+5511999998888'
    phone_number = sender.replace("whatsapp:", "")

    # 1. Verifica se o número do remetente está na lista de autorizados
    if phone_number not in settings.TWILIO_ALLOWED_NUMBERS:
        logger.warning(f"Webhook recebido de número não autorizado: {phone_number}")
        return HttpResponse(status=200)  # Retorna OK, mas não faz nada

    # 2. Busca o usuário padrão definido nas configurações
    try:
        primary_user = User.objects.get(pk=settings.FINANCE_BOT_USER_ID)
    except User.DoesNotExist:
        logger.error(f"Usuário principal do bot (ID: {settings.FINANCE_BOT_USER_ID}) não foi encontrado no banco de dados.")
        return HttpResponse(status=500)

    resp = MessagingResponse()
    user_state_key = get_user_state_key(sender)
    
    # 3. Lógica de conversa baseada em "menu"
    if incoming_msg.lower() == 'menu':
        # Inicia a conversa e aguarda a despesa por 24h
        cache.set(user_state_key, 'awaiting_expense', timeout=86400)
        reply = "Olá! Estou pronto para receber sua despesa no formato: `[valor] [descrição] [categoria] [conta]`"
        resp.message(reply)
    
    elif cache.get(user_state_key) == 'awaiting_expense':
        # Se já aguardava, processa a mensagem como uma despesa
        bot = FinanceBot(sender=sender, user=primary_user)
        reply = bot.process_message(incoming_msg)
        if reply:
            resp.message(reply)
        # Limpa o estado para a próxima interação
        cache.delete(user_state_key)
    
    else:
        # Se não há conversa iniciada, instrui o usuário
        reply = "Para registrar uma nova despesa, envie a palavra `menu`."
        resp.message(reply)

    return HttpResponse(str(resp), content_type="application/xml")
