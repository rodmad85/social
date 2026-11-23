# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _get_channel_vals(self, gateway, token, update):
        """Attach the WhatsApp conversation to the linked livechat channel.

        Incoming WhatsApp messages create a single gateway channel per contact.
        The linked ``im_livechat.channel`` is only used for its configuration
        (operators, IA, chatbot); no separate livechat conversation channel is
        created anymore. The operator and the gateway members are added as
        pinned members so the conversation is visible in Discuss.
        """
        vals = super()._get_channel_vals(gateway, token, update)
        livechat_channel = self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", gateway.id)], limit=1
        )
        if not livechat_channel:
            return vals
        author = self._get_author(gateway, update)
        operator = livechat_channel._get_operator()
        operator_partner = operator.partner_id if operator else False
        member_partner_ids = set(gateway.member_ids.mapped("partner_id").ids)
        if operator_partner:
            member_partner_ids.add(operator_partner.id)
        if author and author._name == "res.partner":
            member_partner_ids.add(author.id)
        existing_partner_ids = {
            command[2].get("partner_id")
            for command in vals.get("channel_member_ids", [])
            if command[0] == Command.CREATE and command[2].get("partner_id")
        }
        member_cmds = list(vals.get("channel_member_ids", []))
        for partner_id in sorted(member_partner_ids - existing_partner_ids):
            member_cmds.append(
                Command.create({"partner_id": partner_id, "unpin_dt": False})
            )
        vals.update(
            {
                "livechat_channel_id": livechat_channel.id,
                "livechat_operator_id": operator_partner
                and operator_partner.id
                or False,
                "anonymous_name": self._whatsapp_get_channel_name(
                    gateway, token, update, author=author
                ),
                "channel_member_ids": member_cmds,
            }
        )
        return vals
