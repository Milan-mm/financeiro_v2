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