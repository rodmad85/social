# Copyright 2026 IOMR - Rodrigo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, models


class MailGatewayAbstract(models.AbstractModel):
    _inherit = "mail.gateway.abstract"

    def _get_channel_vals(self, gateway, token, update):
        author = self._get_author(gateway, update)
        # A conversa nasce apenas com o contato externo. Os usuários internos
        # entram somente quando iniciam a conversa pelo chatter ou quando são
        # atribuídos explicitamente (ver whatsapp_central_settings /
        # mail_gateway_whatsapp_messages). Adicionar gateway.member_ids aqui
        # fazia com que todos os administradores do gateway carregassem todas
        # as conversas no Discuss.
        members = []
        if author:
            members.append(
                Command.create(
                    {
                        "partner_id": author._name == "res.partner" and author.id,
                        "guest_id": author._name == "mail.guest" and author.id,
                    }
                )
            )
        author_name = author.display_name if author and author.display_name else False
        return {
            "name": author_name or token,
            "gateway_channel_token": token,
            "gateway_id": gateway.id,
            "channel_type": "gateway",
            "channel_member_ids": members,
            "company_id": gateway.company_id.id,
        }

    def _get_channel(self, gateway, token, update, force_create=False):
        return super()._get_channel(gateway, token, update, force_create=force_create)
