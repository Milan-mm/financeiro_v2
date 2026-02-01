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
from core.models import QuickExpense, CardStatementInitialBalance

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


def get_pending_expense_key(phone_number):
    """Chave de cache para despesa pendente (aguardando saldo inicial)"""
    return f"pending_expense_{phone_number}"


def get_awaiting_balance_key(phone_number):
    """Chave de cache para sinalizar que estamos aguardando saldo inicial"""
    return f"awaiting_initial_balance_{phone_number}"


def has_month_initial_balance(user, year, month):
    """Verifica se existe saldo inicial para o mês/usuário"""
    return CardStatementInitialBalance.objects.filter(
        user_id=user.id, year=year, month=month
    ).exists()


def set_pending_expense(phone_number, valor, descricao):
    """Armazena uma despesa pendente aguardando saldo inicial"""
    cache_key = get_pending_expense_key(phone_number)
    cache.set(cache_key, {
        'valor': str(valor),
        'descricao': descricao,
        'timestamp': datetime.now().isoformat()
    }, timeout=3600)  # 1 hora de timeout


def get_pending_expense(phone_number):
    """Recupera a despesa pendente"""
    return cache.get(get_pending_expense_key(phone_number))


def clear_pending_expense(phone_number):
    """Remove a despesa pendente"""
    cache.delete(get_pending_expense_key(phone_number))


def set_awaiting_initial_balance(phone_number):
    """Marca que estamos aguardando saldo inicial"""
    cache.set(get_awaiting_balance_key(phone_number), True, timeout=3600)


def is_awaiting_initial_balance(phone_number):
    """Verifica se estamos aguardando saldo inicial"""
    return cache.get(get_awaiting_balance_key(phone_number), False)


def clear_awaiting_balance(phone_number):
    """Limpa a flag de aguardando saldo inicial"""
    cache.delete(get_awaiting_balance_key(phone_number))


def parse_initial_balance(message):
    """
    Parseia uma mensagem como saldo inicial (apenas um valor decimal).
    Retorna o Decimal ou None se inválido.
    """
    valor_str = message.strip().replace(',', '.')
    try:
        valor = Decimal(valor_str)
        if valor < 0:
            return None
        return valor
    except (InvalidOperation, ValueError):
        return None


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


def handle_add_expense(user, phone_number, message):
    """Processa comando de adicionar despesa.
    
    Se for o primeiro lançamento do mês, pede o saldo inicial da fatura.
    Caso contrário, registra a despesa normalmente.
    """
    year, month = get_current_month_year()
    
    # Verifica se existe saldo inicial para este mês
    has_balance = has_month_initial_balance(user, year, month)
    
    if not has_balance:
        # Primeiro lançamento do mês: pede saldo inicial
        valor, descricao = parse_expense_message(message)
        if valor is None or descricao is None:
            return "⚠️ Formato inválido. Use: 15.50 - Almoço"
        
        # Armazena a despesa pendente
        set_pending_expense(phone_number, valor, descricao)
        set_awaiting_initial_balance(phone_number)
        
        return "Este é o primeiro lançamento do mês. Para começar, informe o saldo inicial da sua fatura:"
    
    # Saldo inicial já foi informado, registra a despesa normalmente
    valor, descricao = parse_expense_message(message)
    if valor is None or descricao is None:
        return "⚠️ Formato inválido. Use: 15.50 - Almoço"
    
    QuickExpense.objects.create(user=user, descricao=descricao, valor=valor)
    return f"✅ Lançamento adicionado: R$ {valor:.2f} - {descricao}"


def handle_set_initial_balance(user, phone_number, message):
    """Processa o saldo inicial informado pelo usuário.
    
    Cria o CardStatementInitialBalance e registra a despesa pendente.
    """
    # Parse do saldo inicial
    saldo_inicial = parse_initial_balance(message)
    if saldo_inicial is None:
        return "⚠️ Valor inválido. Use um número (ex: 540.30)"
    
    # Recupera a despesa pendente
    pending = get_pending_expense(phone_number)
    if not pending:
        return "Nenhuma despesa pendente encontrada."
    
    year, month = get_current_month_year()
    
    # Cria/atualiza o saldo inicial
    CardStatementInitialBalance.objects.update_or_create(
        user_id=user.id,
        year=year,
        month=month,
        defaults={'saldo_inicial': saldo_inicial}
    )
    
    # Registra a despesa pendente
    valor = Decimal(pending['valor'])
    descricao = pending['descricao']
    QuickExpense.objects.create(user=user, descricao=descricao, valor=valor)
    
    # Limpa estados
    clear_pending_expense(phone_number)
    clear_awaiting_balance(phone_number)
    
    return f"✅ Saldo inicial de R$ {saldo_inicial:.2f} definido. Lançamento 'R$ {valor:.2f} - {descricao}' adicionado."


def handle_view_statement(user, phone_number, statement_type):
    """Processa comando de consultar extrato.

    Agora lê do modelo QuickExpense (atribuindo consultas ao usuário
    fornecido) para o mês/ano correspondente.
    """
    if statement_type.lower() == "extrato atual":
        year, month = get_current_month_year()
        month_label = "Mês Atual"
    elif statement_type.lower() == "extrato anterior":
        year, month = get_previous_month_year()
        month_label = "Mês Anterior"
    else:
        return None

    user_id = getattr(user, 'id', settings.FINANCE_BOT_USER_ID)

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


def handle_delete_last(user, phone_number):
    """Processa comando de excluir último lançamento (persistido no DB)"""
    year, month = get_current_month_year()
    qs = QuickExpense.objects.filter(user_id=user.id, data__year=year, data__month=month).order_by('-data', '-id')

    last = qs.first()
    if not last:
        return "Nenhum lançamento para excluir."

    valor = last.valor
    descricao = last.descricao
    last.delete()
    return f"🗑️ Último lançamento ('R$ {valor:.2f} - {descricao}') foi removido."


def handle_clear_month(user, phone_number):
    """Processa comando de limpar mês (apaga lançamentos no DB)"""
    year, month = get_current_month_year()
    qs = QuickExpense.objects.filter(user_id=user.id, data__year=year, data__month=month)
    deleted_count, _ = qs.delete()
    return "✔️ Todos os lançamentos do mês atual foram zerados." if deleted_count else "Nenhum lançamento para zerar."


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

    # Verifica se estamos aguardando um saldo inicial
    if is_awaiting_initial_balance(phone_number):
        reply = handle_set_initial_balance(primary_user, phone_number, incoming_msg)
    elif incoming_lower == "menu":
        reply = handle_menu_command(phone_number)

    elif incoming_lower in ["extrato atual", "extrato anterior"]:
        reply = handle_view_statement(primary_user, phone_number, incoming_msg)

    elif incoming_lower == "excluir":
        reply = handle_delete_last(primary_user, phone_number)

    elif incoming_lower == "zerar":
        reply = handle_clear_month(primary_user, phone_number)

    else:
        # Tenta processar como um lançamento de despesa
        reply = handle_add_expense(primary_user, phone_number, incoming_msg)

    if reply:
        resp.message(reply)

    return HttpResponse(str(resp), content_type="application/xml")
