from odoo import Command, models


class MailGatewayAbstract(models.AbstractModel):
    _inherit = "mail.gateway.abstract"

    def _get_channel_vals(self, gateway, token, update):
        author = self._get_author(gateway, update)
        # A conversa nasce apenas com o contato externo. Os usuários internos
        # entram somente quando iniciam a conversa pelo chatter ou quando são
        # atribuídos explicitamente. Adicionar gateway.member_ids aqui fazia
        # com que todos os administradores do gateway carregassem todas as
        # conversas no Discuss.
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
        return {
            "gateway_channel_token": token,
            "gateway_id": gateway.id,
            "channel_type": "gateway",
            "channel_member_ids": members,
            "company_id": gateway.company_id.id,
        }
