# core/webhook.py
import logging
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.core.cache import cache
from twilio.twiml.messaging_response import MessagingResponse
from core.models import QuickExpense

logger = logging.getLogger(__name__)


def get_user_cache_key(phone_number):
    """Cria uma chave de cache única para armazenar despesas do usuário"""
    return f"quick_expenses_{phone_number}"


def get_current_month_year():
    """Retorna a representação do mês/ano atual"""
    today = date.today()
    return (today.year, today.month)


def get_previous_month_year():
    """Retorna a representação do mês/ano anterior"""
    today = date.today()
    if today.month == 1:
        return (today.year - 1, 12)
    return (today.year, today.month - 1)


def parse_expense_message(message):
    """
    Parseia uma mensagem no formato: [valor] - [descrição]
    Retorna tupla (valor_decimal, descrição) ou (None, None) se inválido
    """
    # Padrão: número (com ponto ou vírgula) - resto da mensagem
    pattern = r'^([\d.,]+)\s*-\s*(.+)$'
    match = re.match(pattern, message.strip())
    
    if not match:
        return None, None
    
    valor_str = match.group(1).replace(',', '.')
    descricao = match.group(2).strip()
    
    try:
        valor = Decimal(valor_str)
        if valor <= 0:
            return None, None
        return valor, descricao
    except (InvalidOperation, ValueError):
        return None, None


def get_cached_expenses(phone_number, month_year=None):
    """
    Recupera despesas em cache para um mês específico ou atual
    """
    if month_year is None:
        month_year = get_current_month_year()
    
    cache_key = get_user_cache_key(phone_number)
    all_expenses = cache.get(cache_key, {})
    
    month_key = f"{month_year[0]}-{month_year[1]:02d}"
    return all_expenses.get(month_key, [])


def add_cached_expense(phone_number, valor, descricao):
    """
    Adiciona uma despesa ao cache do mês atual
    """
    cache_key = get_user_cache_key(phone_number)
    all_expenses = cache.get(cache_key, {})
    
    month_year = get_current_month_year()
    month_key = f"{month_year[0]}-{month_year[1]:02d}"
    
    if month_key not in all_expenses:
        all_expenses[month_key] = []
    
    # Adiciona a despesa com timestamp para manter ordem
    expense_entry = {
        'valor': str(valor),
        'descricao': descricao,
        'timestamp': datetime.now().isoformat()
    }
    all_expenses[month_key].append(expense_entry)
    
    # Define timeout de 30 dias para o cache
    cache.set(cache_key, all_expenses, timeout=30*24*3600)


def remove_last_cached_expense(phone_number):
    """
    Remove a última despesa adicionada ao mês atual
    Retorna a despesa removida ou None se não houver
    """
    cache_key = get_user_cache_key(phone_number)
    all_expenses = cache.get(cache_key, {})
    
    month_year = get_current_month_year()
    month_key = f"{month_year[0]}-{month_year[1]:02d}"
    
    if month_key in all_expenses and all_expenses[month_key]:
        removed = all_expenses[month_key].pop()
        cache.set(cache_key, all_expenses, timeout=30*24*3600)
        return removed
    
    return None


def clear_month_cached_expenses(phone_number):
    """
    Limpa todas as despesas do mês atual do cache
    """
    cache_key = get_user_cache_key(phone_number)
    all_expenses = cache.get(cache_key, {})
    
    month_year = get_current_month_year()
    month_key = f"{month_year[0]}-{month_year[1]:02d}"
    
    if month_key in all_expenses:
        all_expenses[month_key] = []
        cache.set(cache_key, all_expenses, timeout=30*24*3600)


def format_expense_list(expenses, month_label="Mês Atual"):
    """
    Formata uma lista de despesas em cache para exibição
    """
    if not expenses:
        return f"Nenhum lançamento para o {month_label.lower()}."
    
    total = Decimal('0')
    lines = [f"📝 Extrato {month_label}:"]
    
    for expense in expenses:
        valor = Decimal(expense['valor'])
        descricao = expense['descricao']
        lines.append(f"- R$ {valor:.2f} - {descricao}")
        total += valor
    
    lines.append(f"\nTotal: R$ {total:.2f}")
    return "\n".join(lines)


def handle_menu_command(phone_number):
    """Retorna o menu de opções"""
    menu_text = """Olá! Escolha uma opção:
- Lançar despesa: [valor] [descrição]
- Consultar extrato: "extrato atual" ou "extrato anterior"
- Excluir último lançamento: "excluir"
- Limpar mês atual: "zerar\""""
    return menu_text


def handle_add_expense(phone_number, message):
    """Processa comando de adicionar despesa"""
    valor, descricao = parse_expense_message(message)
    
    if valor is None or descricao is None:
        return "⚠️ Formato inválido. Use: 15.50 - Almoço"
    
    add_cached_expense(phone_number, valor, descricao)
    return f"✅ Lançamento adicionado: R$ {valor:.2f} - {descricao}"


def handle_view_statement(phone_number, statement_type):
    """Processa comando de consultar extrato.

    Agora lê do modelo QuickExpense (atribuindo consultas ao usuário
    definido em `settings.FINANCE_BOT_USER_ID`) para o mês/ano correspondente.
    """
    if statement_type.lower() == "extrato atual":
        year, month = get_current_month_year()
        month_label = "Mês Atual"
    elif statement_type.lower() == "extrato anterior":
        year, month = get_previous_month_year()
        month_label = "Mês Anterior"
    else:
        return None

    try:
        user_id = int(settings.FINANCE_BOT_USER_ID)
    except Exception:
        user_id = settings.FINANCE_BOT_USER_ID

    qs = QuickExpense.objects.filter(user_id=user_id, data__year=year, data__month=month).order_by('data', 'id')

    # Converte queryset para lista compatível com format_expense_list
    expenses = []
    for q in qs:
        expenses.append({
            'valor': str(q.valor),
            'descricao': q.descricao,
            'timestamp': q.data.isoformat(),
        })

    return format_expense_list(expenses, month_label)


def handle_delete_last(phone_number):
    """Processa comando de excluir último lançamento"""
    removed = remove_last_cached_expense(phone_number)
    
    if removed is None:
        return "Nenhum lançamento para excluir."
    
    valor = Decimal(removed['valor'])
    descricao = removed['descricao']
    return f"🗑️ Último lançamento ('R$ {valor:.2f} - {descricao}') foi removido."


def handle_clear_month(phone_number):
    """Processa comando de limpar mês"""
    clear_month_cached_expenses(phone_number)
    return "✔️ Todos os lançamentos do mês atual foram zerados."


@csrf_exempt
@require_POST
def twilio_webhook(request):
    incoming_msg = request.POST.get("Body", "").strip()
    sender = request.POST.get("From", "")  # Ex: 'whatsapp:+5511999998888'
    phone_number = sender.replace("whatsapp:", "")

    # 1. Verifica se o número do remetente está na lista de autorizados
    if phone_number not in settings.TWILIO_ALLOWED_NUMBERS:
        logger.warning(f"Webhook recebido de número não autorizado: {phone_number}")
        return HttpResponse(status=200)

    # 2. Busca o usuário padrão definido nas configurações
    try:
        primary_user = User.objects.get(pk=settings.FINANCE_BOT_USER_ID)
    except User.DoesNotExist:
        logger.error(f"Usuário principal do bot (ID: {settings.FINANCE_BOT_USER_ID}) não foi encontrado no banco de dados.")
        return HttpResponse(status=500)

    resp = MessagingResponse()
    reply = None

    # 3. Processamento dos comandos
    incoming_lower = incoming_msg.lower()

    if incoming_lower == "menu":
        reply = handle_menu_command(phone_number)

    elif incoming_lower in ["extrato atual", "extrato anterior"]:
        reply = handle_view_statement(phone_number, incoming_msg)

    elif incoming_lower == "excluir":
        reply = handle_delete_last(phone_number)

    elif incoming_lower == "zerar":
        reply = handle_clear_month(phone_number)

    else:
        # Tenta processar como um lançamento de despesa
        reply = handle_add_expense(phone_number, incoming_msg)

    if reply:
        resp.message(reply)

    return HttpResponse(str(resp), content_type="application/xml")
