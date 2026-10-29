# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    whatsapp_gateway_id = fields.Many2one(
        "mail.gateway",
        string="WhatsApp Gateway",
        domain=[("gateway_type", "=", "whatsapp")],
        help="When a WhatsApp gateway is linked, incoming WhatsApp messages "
        "will be routed through this livechat channel.",
    )
    whatsapp_chatbot_script_id = fields.Many2one(
        "chatbot.script",
        string="WhatsApp Bot Script",
        help="Scripted questions automatically sent to the customer on the "
        "first WhatsApp contact. The customer's answers (including the "
        "interactive buttons) drive the script; when it ends, or when an "
        "attendant replies, the bot stops and the attendants take over.",
    )

    ai_enabled = fields.Boolean(string="Habilitar IA")
    ai_after_script = fields.Boolean(string="IA após script", default=True)
    ai_connection_id = fields.Many2one("ai.connection", string="Conexão IA")
    ai_model = fields.Char(string="Modelo IA")
    ai_tool_ids = fields.Many2many("ai.tool", string="Ferramentas permitidas")
    ai_history_limit = fields.Integer(string="Limite histórico", default=10)
    ai_handoff_keywords = fields.Char(
        string="Palavras-chave para handoff",
        default="atendente,human,humano,falar com humano,operador,transferir,pessoa",
    )
    ai_open_hour = fields.Float(string="Abertura")
    ai_close_hour = fields.Float(string="Encerramento")
    ai_lunch_start_hour = fields.Float(string="Início intervalo almoço")
    ai_lunch_end_hour = fields.Float(string="Fim intervalo almoço")
    ai_capabilities_text = fields.Text(
        string="O que pode ser acessado",
        default="Consultar horários disponíveis da agenda.\nConsultar tabela de preços padrão.",
    )
    ai_faq_list = fields.Text(
        string="Perguntas principais",
        default="Quais horários tem disponíveis?\nQuanto custa este serviço?\nTem vaga para hoje?",
    )
    ai_notice_message = fields.Text(
        string="Mensagem aviso IA",
        default="*Atendimento com Assistente Virtual*\n\nNeste momento você está sendo atendido pela nossa assistente virtual.\n\n*Horário:* {open} às {close}\n*Intervalo de almoço:* {lunch_start} às {lunch_end}\n\n*Posso te ajudar com:*\n{capabilities}\n\nSe preferir falar com um atendente humano, basta responder: *atendente* ou *humano*.",
    )
    ai_transfer_message = fields.Text(
        string="Mensagem de transferência",
        default="Estou transferindo você para um atendente humano. Aguarde um momento.",
    )
    ai_system_prompt = fields.Text(
        string="Prompt do sistema",
        default="Você é o assistente virtual do Livechat WhatsApp desta clínica.\n\nOBJETIVO: Atender APENAS sobre agenda/horários disponíveis e tabela de preços padrão.\n\nREGRAS RIGIDAS:\n- NUNCA crie, edite ou cancele agendamentos, orçamentos, pedidos de venda, leads ou contatos.\n- NUNCA solicite CPF, dados completos de cartão ou senhas.\n- SEMPRE use as ferramentas disponíveis quando perguntarem sobre horários ou valores.\n- SE NÃO TIVER CERTEZA ou a pergunta sair do escopo -> TRANSFERIR PARA ATENDENTE HUMANO.\n- SE CLIENTE PEDIR \"ATENDENTE\", \"HUMANO\", \"FALAR COM ALGUÉM\" -> TRANSFERIR IMEDIATAMENTE.\n- Responda em português do Brasil, curto e objetivo.\n- Não invente preços ou horários. Se não encontrar resultado nas ferramentas, transfira.\n- Informe horário de atendimento e intervalo de almoço quando fizer sentido.\n\nINFORMAÇÕES:\n- Horário: {OPEN} às {CLOSE}\n- Almoço: {LUNCH_START} às {LUNCH_END}\n- O que pode ser consultado: {CAPABILITIES}\n- Perguntas principais: {FAQ}",
    )
