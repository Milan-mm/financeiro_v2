# core/utils_webhook.py
import logging
from decimal import Decimal, InvalidOperation
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone
from .models import QuickExpense, SystemLog  # <--- Importamos o SystemLog

logger = logging.getLogger(__name__)


class FinanceBot:
    def __init__(self, sender, user):
        self.sender = sender
        self.user = user
        self.cache_key_state = f"wpp_state_{sender}"
        self.cache_key_data = f"wpp_data_{sender}"
        self.cache_key_balance = f"wpp_balance_{sender}"

    # ... (Métodos auxiliares _get_state, _set_state, etc. mantêm-se iguais) ...
    def _get_state(self):
        return cache.get(self.cache_key_state)

    def _set_state(self, state, timeout=600):
        cache.set(self.cache_key_state, state, timeout)

    def _get_temp_data(self):
        return cache.get(self.cache_key_data) or {}

    def _update_temp_data(self, **kwargs):
        data = self._get_temp_data()
        data.update(kwargs)
        cache.set(self.cache_key_data, data, 600)

    def _clear_state(self):
        cache.delete(self.cache_key_state)
        cache.delete(self.cache_key_data)

    def _get_initial_balance(self):
        return Decimal(cache.get(self.cache_key_balance) or "0.00")

    def _set_initial_balance(self, value):
        cache.set(self.cache_key_balance, str(value), timeout=60 * 60 * 24 * 30)

    def process_message(self, incoming_msg):
        # 1. LOG DE SEGURANÇA (Grava tudo o que chega)
        # Assim garantimos que "qqr msg recebida" fica registada no banco
        try:
            SystemLog.objects.create(
                level=SystemLog.LEVEL_INFO,
                source=SystemLog.SOURCE_BACKEND,
                message=f"Webhook msg de {self.sender}",
                details=incoming_msg
            )
        except Exception as e:
            logger.error(f"Falha ao criar SystemLog: {e}")

        state = self._get_state()
        msg = incoming_msg.strip().lower()

        # 2. Comandos Globais
        if msg in ['menu', 'cancelar', 'sair', 'oi', 'ola']:
            self._clear_state()
            return self.menu_options()

        # 3. Máquina de Estados (Se já estiver num fluxo)
        if state == 'WAIT_BALANCE':
            return self.handle_wait_balance(msg)
        elif state == 'WAIT_VALUE':
            return self.handle_wait_value(msg)
        elif state == 'WAIT_DESC':
            return self.handle_wait_desc(msg)

        # 4. Menu Principal (Seleção Numérica)
        if msg == '1':
            self._set_state('WAIT_VALUE')
            return "💰 *Novo Gasto*\nDigite o *valor* (ex: 15,90):"
        elif msg == '2':
            return self.get_history()
        elif msg == '3':
            self._set_state('WAIT_BALANCE')
            return "🔄 *Reiniciar/Definir Saldo*\nDigite o saldo inicial:"
        elif msg == '4':
            return self.delete_last_expense()

        # 5. SMART ENTRY (Captura qualquer outra mensagem)
        # Se chegou aqui, não é comando nem número do menu.
        # Vamos tentar salvar como Gasto!
        return self.handle_smart_entry(incoming_msg)

    # --- Handlers ---

    def handle_smart_entry(self, text):
        """
        Tenta adivinhar se o usuário mandou um VALOR ou uma DESCRIÇÃO
        para iniciar o lançamento sem precisar digitar '1'.
        """
        # Tenta interpretar como número (Valor)
        try:
            clean_text = text.replace('r$', '').replace(' ', '').replace(',', '.')
            val = Decimal(clean_text)
            # Se funcionou, é um valor!
            self._update_temp_data(valor=str(val))
            self._set_state('WAIT_DESC')
            return f"Entendi: *R$ {val:.2f}* 💸\nAgora, diz-me a *descrição*:"
        except InvalidOperation:
            # Se falhou, assumimos que é texto (Descrição)
            # Mas ignoramos textos muito curtos para evitar lixo
            if len(text) < 2:
                return self.menu_options()

            self._update_temp_data(descricao=text.title())
            self._set_state('WAIT_VALUE')
            return f"Entendi: *{text.title()}* 📝\nAgora, qual foi o *valor*?"

    def handle_wait_value(self, text):
        try:
            clean_text = text.replace('r$', '').replace(' ', '').replace(',', '.')
            val = Decimal(clean_text)

            # Verifica se já temos descrição pendente (do fluxo Smart Entry)
            data = self._get_temp_data()
            if 'descricao' in data:
                # Já temos tudo, salvar direto!
                return self._save_expense(val, data['descricao'])
            else:
                # Fluxo normal (Opção 1): Guardar valor e pedir descrição
                self._update_temp_data(valor=str(val))
                self._set_state('WAIT_DESC')
                return f"Ok, *R$ {val:.2f}*.\nAgora, qual a *descrição*?"
        except InvalidOperation:
            return "⚠️ Valor inválido. Digite apenas números."

    def handle_wait_desc(self, text):
        data = self._get_temp_data()
        # Verifica se temos valor pendente
        if 'valor' in data:
            valor = Decimal(data['valor'])
            return self._save_expense(valor, text.title())
        else:
            # Caso raro de erro de estado
            self._clear_state()
            return "⚠️ Ocorreu um erro no fluxo. Tente novamente."

    def _save_expense(self, valor, descricao):
        # Lógica centralizada de salvamento
        QuickExpense.objects.create(
            user=self.user,
            descricao=descricao,
            valor=valor
        )
        self._clear_state()

        total_mes = self.get_monthly_total()
        base = self._get_initial_balance()
        return (
            f"✅ *Salvo!*\n"
            f"{descricao} - R$ {valor:.2f}\n\n"
            f"📈 Acumulado Mês: *R$ {(base + total_mes):.2f}*"
        )

    # ... (Manter handle_wait_balance, get_monthly_total, get_history, delete_last_expense iguais) ...
    # Se precisares que eu repita essas funções, avisa! Onde "..." está, o código é o mesmo da versão anterior.

    # [Inclua aqui o resto dos métodos da resposta anterior se não os tiver copiado]
    def handle_wait_balance(self, text):
        try:
            val_str = text.replace(',', '.')
            val = Decimal(val_str)
            self._set_initial_balance(val)
            self._clear_state()
            return f"✅ Base definida: *R$ {val:.2f}*."
        except InvalidOperation:
            return "⚠️ Valor inválido."

    def get_monthly_total(self):
        hoje = timezone.now()
        total = QuickExpense.objects.filter(
            user=self.user,
            data__month=hoje.month,
            data__year=hoje.year
        ).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
        return total

    def get_history(self):
        hoje = timezone.now()
        items = QuickExpense.objects.filter(
            user=self.user,
            data__month=hoje.month,
            data__year=hoje.year
        ).order_by('-data', '-id')[:15]

        if not items:
            return "📭 Nenhum gasto este mês."

        msg = [f"📜 *Extrato de {hoje.strftime('%B').capitalize()}*\n"]
        for item in items:
            msg.append(f"▫️ {item.data.day} - {item.descricao}: R$ {item.valor:.2f}")

        total = self.get_monthly_total()
        base = self._get_initial_balance()
        msg.append(f"\n💰 Gastos: R$ {total:.2f}")
        if base > 0:
            msg.append(f"🏁 *Total: R$ {(total + base):.2f}*")

        return "\n".join(msg)

    def delete_last_expense(self):
        last_item = QuickExpense.objects.filter(user=self.user).last()
        if last_item:
            details = f"{last_item.descricao} (R$ {last_item.valor:.2f})"
            last_item.delete()
            return f"🗑️ *Apagado:*\n{details}"
        return "⚠️ Nada para apagar."

    def menu_options(self):
        self._clear_state()
        total = self.get_monthly_total() + self._get_initial_balance()
        return (
            f"🤖 *Financeiro Bot*\n"
            f"Total Mês: R$ {total:.2f}\n"
            "━━━━━━━━━━━━━━━━\n"
            "1️⃣  Lançar Gasto\n"
            "2️⃣  Histórico\n"
            "3️⃣  Definir Saldo Inicial\n"
            "4️⃣  Excluir Último\n"
            "━━━━━━━━━━━━━━━━\n"
            "💡 *Dica:* Podes digitar direto o valor ou o nome do gasto!"
        )