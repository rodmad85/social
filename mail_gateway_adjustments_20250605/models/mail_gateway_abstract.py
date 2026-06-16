from odoo import Command, models


class MailGatewayAbstract(models.AbstractModel):
    _inherit = "mail.gateway.abstract"

    def _get_channel_vals(self, gateway, token, update):
        author = self._get_author(gateway, update)
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

    def _get_channel(self, gateway, token, update, force_create=False):
        chat_id = gateway._get_channel_id(token)
        if chat_id:
            return gateway.env["discuss.channel"].browse(chat_id)
        if not force_create and gateway.has_new_channel_security:
            return False
        channel = gateway.env["discuss.channel"].create(
            self._get_channel_vals(gateway, token, update)
        )
        return channel
