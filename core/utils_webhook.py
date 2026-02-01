# core/utils_webhook.py
import logging
from decimal import Decimal, InvalidOperation
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from .models import QuickExpense, SystemLog

logger = logging.getLogger(__name__)


class FinanceBot:
    def __init__(self, sender, user):
        self.sender = sender
        self.user = user
        self.cache_key_state = f"wpp_state_{sender}"
        self.cache_key_data = f"wpp_data_{sender}"
        self.cache_key_balance = f"wpp_balance_{sender}"

    # =========================
    # Cache helpers
    # =========================
    def _get_state(self):
        return cache.get(self.cache_key_state)

    def _set_state(self, state, timeout=600):
        cache.set(self.cache_key_state, state, timeout)

    def _clear_state(self):
        cache.delete(self.cache_key_state)
        cache.delete(self.cache_key_data)

    def _get_initial_balance(self):
        return Decimal(cache.get(self.cache_key_balance) or "0.00")

    def _set_initial_balance(self, value):
        cache.set(self.cache_key_balance, str(value), 60 * 60 * 24 * 30)

    # =========================
    # ENTRY POINT
    # =========================
    def process_message(self, incoming_msg):
        # 1. Log incoming message for audit purposes
        try:
            SystemLog.objects.create(
                level=SystemLog.LEVEL_INFO,
                source=SystemLog.SOURCE_BACKEND,
                message=f"Webhook msg from {self.sender}",
                details=incoming_msg,
            )
        except Exception as e:
            logger.error(f"Failed to create SystemLog: {e}")

        msg = (incoming_msg or "").strip().lower()
        state = self._get_state()

        # 2. Universal commands
        if msg in ("cancelar", "sair"):
            self._clear_state()
            return "Operação cancelada."

        if msg == "menu":
            self._clear_state()
            self._set_state("AWAITING_MENU_CHOICE")
            return self.menu_options()

        # 3. State-based handlers
        if state == "AWAITING_MENU_CHOICE":
            return self.handle_menu_choice(msg)
        elif state == "AWAITING_EXPENSE_AMOUNT":
            return self.handle_expense_amount(msg)
        elif state == "AWAITING_INITIAL_BALANCE":
            return self.handle_initial_balance(msg)

        # 4. If no state, ignore the message
        logger.info(
            "Ignored message (no active state)",
            extra={"from": self.sender, "body": msg},
        )
        return ""  # No response if no state and not a 'menu' command

    # =========================
    # STATE HANDLERS
    # =========================

    def handle_menu_choice(self, msg):
        if msg == "1":
            self._set_state("AWAITING_EXPENSE_AMOUNT")
            return "✏️ Qual o valor do gasto?"
        elif msg == "2":
            self._clear_state()
            return self.get_history()
        elif msg == "3":
            self._set_state("AWAITING_INITIAL_BALANCE")
            return "💰 Qual o saldo inicial a ser definido?"
        elif msg == "4":
            self._clear_state()
            return self.delete_last_expense()
        else:
            return "Opção inválida. Por favor, envie um número de 1 a 4, ou 'menu' para recomeçar."

    def handle_expense_amount(self, msg):
        try:
            # Replace comma with dot for decimal conversion
            value_str = msg.replace(",", ".")
            amount = Decimal(value_str)

            QuickExpense.objects.create(user=self.user, valor=amount, descricao="Via Bot")
            self._clear_state()
            total = self.get_monthly_total() + self._get_initial_balance()
            return f"✅ Gasto de R$ {amount:.2f} lançado!\n\n💰 Total do mês: *R$ {total:.2f}*"
        except InvalidOperation:
            return "Valor inválido. Por favor, envie apenas o número (ex: 25,50)."

    def handle_initial_balance(self, msg):
        try:
            value_str = msg.replace(",", ".")
            amount = Decimal(value_str)
            self._set_initial_balance(amount)
            self._clear_state()
            return f"saldo inicial definido para R$ {amount:.2f}."
        except InvalidOperation:
            return "Valor inválido. Por favor, envie apenas o número (ex: 1500,00)."

    # =========================
    # FEATURE FUNCTIONS
    # =========================

    def get_monthly_total(self):
        today = timezone.now()
        return (
            QuickExpense.objects.filter(
                user=self.user,
                data__month=today.month,
                data__year=today.year,
            ).aggregate(Sum("valor"))["valor__sum"]
            or Decimal("0.00")
        )

    def menu_options(self):
        total = self.get_monthly_total() + self._get_initial_balance()
        return (
            "🤖 *Financeiro Bot*\n"
            f"💰 Total do mês: *R$ {total:.2f}*\n"
            "━━━━━━━━━━━━━━━━\n"
            "1️⃣  Lançar Gasto\n"
            "2️⃣  Histórico\n"
            "3️⃣  Definir Saldo Inicial\n"
            "4️⃣  Excluir Último\n"
            "━━━━━━━━━━━━━━━━\n"
            "ℹ️ Envie 'cancelar' a qualquer momento para sair."
        )

    def get_history(self):
        expenses = QuickExpense.objects.filter(user=self.user).order_by("-data")[:5]
        if not expenses:
            return "Nenhum gasto rápido encontrado."

        lines = ["*Últimos 5 gastos:*"]
        for exp in expenses:
            lines.append(f"- R$ {exp.valor:.2f} em {exp.data.strftime('%d/%m')}")
        return "\n".join(lines)

    def delete_last_expense(self):
        last_expense = QuickExpense.objects.filter(user=self.user).order_by("-data").first()
        if last_expense:
            amount = last_expense.valor
            last_expense.delete()
            return f"🗑️ Último gasto de R$ {amount:.2f} foi excluído."
        return "Nenhum gasto para excluir."
