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
        """
        REGRA DE OURO:
        - Só responde se for 'menu'
        - fTodo o resto apenas loga
        """

        # 1️⃣ LOG ABSOLUTO (SEGURANÇA / AUDITORIA)
        try:
            SystemLog.objects.create(
                level=SystemLog.LEVEL_INFO,
                source=SystemLog.SOURCE_BACKEND,
                message=f"Webhook msg de {self.sender}",
                details=incoming_msg,
            )
        except Exception as e:
            logger.error(f"Falha ao criar SystemLog: {e}")

        msg = (incoming_msg or "").strip().lower()

        # 2️⃣ ÚNICA RESPOSTA PERMITIDA
        if msg == "menu":
            self._clear_state()
            return self.menu_options()

        # 3️⃣ Opcional: comandos silenciosos
        if msg in ("cancelar", "sair"):
            self._clear_state()
            return ""

        # 4️⃣ fTODO O RESTO É IGNORADO
        logger.info(
            "Mensagem ignorada (modo furtivo ativo)",
            extra={"from": self.sender, "body": msg},
        )
        return ""

    # =========================
    # FUNÇÕES ABAIXO FICAM
    # (DESATIVADAS PELO FLUXO)
    # =========================

    def get_monthly_total(self):
        hoje = timezone.now()
        return (
            QuickExpense.objects.filter(
                user=self.user,
                data__month=hoje.month,
                data__year=hoje.year,
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
            "ℹ️ *Envie apenas `menu` para interagir*"
        )
