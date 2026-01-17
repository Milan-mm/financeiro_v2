# core/views.py
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.contrib.auth.models import User
from twilio.twiml.messaging_response import MessagingResponse

from core.utils_webhook import FinanceBot

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def twilio_webhook(request):
    incoming_msg = request.POST.get("Body", "")
    sender = request.POST.get("From")

    # Ajuste conforme sua lógica real
    user = User.objects.first()

    bot = FinanceBot(sender=sender, user=user)
    reply = bot.process_message(incoming_msg)

    resp = MessagingResponse()

    # 🔐 Só responde se houver texto (ou seja: apenas "menu")
    if reply:
        resp.message(reply)

    return HttpResponse(str(resp), content_type="application/xml")
