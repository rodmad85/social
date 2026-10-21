import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Parâmetros preenchidos pelo módulo whatsapp_central_settings. São lidos
# diretamente para não criar dependência circular (o módulo de configurações
# depende deste).
PARAM_UNASSIGNED_ACTION = "whatsapp_central_settings.wa_unassigned_action"
PARAM_UNASSIGNED_USER = "whatsapp_central_settings.wa_unassigned_user_id"


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _get_message_body(self, record):
        body = super()._get_message_body(record)
        author = record.mail_message_id.author_id
        if author and body:
            body = f"*{author.name}*\n\n{body}"
        return body

    def _get_author(self, gateway, update):
        author = super()._get_author(gateway, update)
        if author and author._name == "res.partner":
            return author
        messages = update.get("messages")
        if not messages:
            return author
        author_id = messages[0].get("from")
        if author_id:
            candidates = [str(author_id)]
            if len(str(author_id)) == 12:
                candidates.append(str(author_id)[:4] + "9" + str(author_id)[4:])
            elif len(str(author_id)) == 13:
                candidates.append(str(author_id)[:4] + str(author_id)[5:])
            for candidate in candidates:
                wp = self.env["res.partner.whatsapp.phone"].search(
                    [
                        ("phone_sanitized", "=like", "%" + candidate[-8:]),
                    ],
                    limit=1,
                )
                if wp:
                    partner = wp.partner_id
                    self.env["res.partner.gateway.channel"]._get_or_create_for_gateway(
                        partner, gateway, str(author_id)
                    )
                    return partner
        return author

    def _receive_update(self, gateway, update):
        affected_phones = set()
        first_value = None
        has_messages = False
        if update:
            for entry in update["entry"]:
                for change in entry["changes"]:
                    if change["field"] != "messages":
                        continue
                    if first_value is None:
                        first_value = change["value"]
                    if change["value"].get("messages"):
                        has_messages = True
                    for message in change["value"].get("messages", []):
                        if message.get("from"):
                            affected_phones.add(message["from"])
        super()._receive_update(gateway, update)
        author = (
            self._get_author(gateway, first_value)
            if first_value and has_messages
            else False
        )
        for phone in affected_phones:
            channel = self._get_channel_by_phone_or_partner(gateway, phone, author)
            if not channel:
                continue
            if author and author._name == "res.partner":
                if not channel.name:
                    suffix = self._get_phone_description(phone)
                    channel.name = (
                        f"{author.display_name} ({suffix})"
                        if suffix
                        else author.display_name
                    )
            # Atribui somente quando ainda não há usuário interno responsável.
            # Se alguém iniciou a conversa pelo chatter ou já foi atribuído, a
            # resposta é entregue apenas a essa pessoa.
            self._assign_default_user(channel)

    def _get_channel_by_phone_or_partner(self, gateway, phone, author=None):
        tokens_to_try = [str(phone)]
        if not str(phone).startswith("+"):
            tokens_to_try.append("+" + str(phone))
        if len(str(phone)) == 12:
            tokens_to_try.append(str(phone)[:4] + "9" + str(phone)[4:])
        elif len(str(phone)) == 13:
            tokens_to_try.append(str(phone)[:4] + str(phone)[5:])
        for candidate in tokens_to_try:
            chat_id = gateway._get_channel_id(candidate)
            if chat_id:
                channel = self.env["discuss.channel"].browse(chat_id)
                if channel.exists():
                    return channel
        if author and author._name == "res.partner":
            gc = self.env["res.partner.gateway.channel"].search(
                [
                    ("partner_id", "=", author.id),
                    ("gateway_id", "=", gateway.id),
                ],
                limit=1,
            )
            if gc:
                for candidate in tokens_to_try:
                    chat_id = gateway._get_channel_id(candidate)
                    if chat_id:
                        channel = self.env["discuss.channel"].browse(chat_id)
                        if channel.exists():
                            return channel
                chat_id = gateway._get_channel_id(gc.gateway_token)
                if chat_id:
                    channel = self.env["discuss.channel"].browse(chat_id)
                    if channel.exists():
                        return channel
        return False

    def _get_phone_description(self, phone):
        phone_str = str(phone)
        candidates = [phone_str]
        if len(phone_str) == 12:
            candidates.append(phone_str[:4] + "9" + phone_str[4:])
        elif len(phone_str) == 13:
            candidates.append(phone_str[:4] + phone_str[5:])
        for candidate in candidates:
            wp = self.env["res.partner.whatsapp.phone"].search(
                [
                    ("phone_sanitized", "=like", "%" + candidate[-8:]),
                ],
                limit=1,
            )
            if wp and wp.description:
                return wp.description
        return False

    def _get_unassigned_default_user(self):
        """Usuário padrão configurado em Definições › WhatsApp Central.

        A configuração "Mensagens não atribuídas" define se a conversa fica na
        lista (``list``) ou é atribuída diretamente a um usuário (``assign``).
        """
        params = self.env["ir.config_parameter"].sudo()
        if (params.get_param(PARAM_UNASSIGNED_ACTION) or "list") != "assign":
            return self.env["res.users"]
        raw_user_id = params.get_param(PARAM_UNASSIGNED_USER)
        if not raw_user_id:
            return self.env["res.users"]
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            _logger.warning(
                "Parâmetro %s inválido: %r", PARAM_UNASSIGNED_USER, raw_user_id
            )
            return self.env["res.users"]
        user = self.env["res.users"].sudo().browse(user_id).exists()
        if not user or not user.active:
            _logger.warning(
                "Usuário padrão de mensagens não atribuídas inexistente ou "
                "inativo (id=%s). A conversa permanecerá na lista.",
                user_id,
            )
            return self.env["res.users"]
        if not user.has_group("mail_gateway.gateway_user"):
            _logger.warning(
                "Usuário %s não pertence ao grupo Gateway; a conversa "
                "permanecerá na lista de não atribuídas.",
                user.name,
            )
            return self.env["res.users"]
        return user

    def _assign_default_user(self, channel):
        """Atribui a conversa ao usuário padrão quando ninguém a assumiu.

        Não faz nada quando o canal já possui um usuário interno ativo — nesse
        caso a conversa pertence a quem iniciou pelo chatter ou a quem foi
        atribuído posteriormente.
        """
        if not channel or channel.channel_type != "gateway":
            return
        has_active_user = bool(
            self.env["discuss.channel.member"]
            .sudo()
            .search_count(
                [
                    ("channel_id", "=", channel.id),
                    ("partner_id.user_ids.active", "=", True),
                ]
            )
        )
        if has_active_user:
            return
        user = self._get_unassigned_default_user()
        if not user:
            return
        member = (
            self.env["discuss.channel.member"]
            .sudo()
            .search(
                [
                    ("channel_id", "=", channel.id),
                    ("partner_id", "=", user.partner_id.id),
                ],
                limit=1,
            )
        )
        if not member:
            self.env["discuss.channel.member"].sudo().create(
                {
                    "channel_id": channel.id,
                    "partner_id": user.partner_id.id,
                    "is_pinned": False,
                    "unpin_dt": False,
                }
            )
