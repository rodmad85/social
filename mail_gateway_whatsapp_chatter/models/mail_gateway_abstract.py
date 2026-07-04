from odoo import Command, models


class MailGatewayAbstract(models.AbstractModel):
    _inherit = "mail.gateway.abstract"

    def _get_channel_vals(self, gateway, token, update):
        author = self._get_author(gateway, update)
        members = [
            Command.create({"partner_id": p.id, "unpin_dt": False})
            for p in gateway.member_ids.partner_id
        ]
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
        return super()._get_channel(gateway, token, update, force_create=force_create)
