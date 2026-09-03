# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import Command, api, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    @api.model
    def _get_livechat_whatsapp_channel_vals(self, gateway, token, update):
        """Build channel vals for a livechat channel linked to a WhatsApp
        gateway.

        This method creates a ``discuss.channel`` with
        ``channel_type='livechat'`` instead of the default
        ``channel_type='gateway'`` used by the base ``mail_gateway`` module.
        The operator is selected via the livechat channel's ``_get_operator``
        method, and the channel is linked to the WhatsApp gateway so that
        outbound messages are routed through WhatsApp.
        """
        livechat_channel = gateway.livechat_channel_id
        user_operator = livechat_channel._get_operator()
        if not user_operator:
            _logger.warning("No livechat operator available for gateway %s", gateway.id)
            return {}
        author = self.env["mail.gateway.whatsapp"]._get_author(gateway, update)
        name = token
        for contact in update.get("contacts", []):
            if contact.get("wa_id") == token:
                name = contact.get("profile", {}).get("name", token)
                break
        member_cmds = [
            Command.create({"partner_id": partner.id, "unpin_dt": False})
            for partner in gateway.member_ids.partner_id
        ]
        if author:
            if author._name == "res.partner":
                member_cmds.append(Command.create({"partner_id": author.id}))
            elif author._name == "mail.guest":
                member_cmds.append(Command.create({"guest_id": author.id}))
        channel_name = " ".join(
            filter(
                None,
                [
                    name,
                    user_operator.livechat_username or user_operator.name,
                ],
            )
        )
        return {
            "name": channel_name,
            "channel_type": "livechat",
            "livechat_active": True,
            "livechat_channel_id": livechat_channel.id,
            "livechat_operator_id": user_operator.partner_id.id,
            "gateway_channel_token": token,
            "gateway_id": gateway.id,
            "anonymous_name": name,
            "channel_member_ids": member_cmds,
            "company_id": gateway.company_id.id or False,
        }

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, *, message_type="notification", **kwargs):
        """When a message is posted on a livechat channel linked to a WhatsApp
        gateway, ensure a gateway notification is created so the message is
        sent through WhatsApp.

        The base ``mail_gateway`` module only creates gateway notifications for
        channels with ``channel_type='gateway'``. This override extends that
        behaviour to livechat channels that have an associated WhatsApp gateway.
        """
        message = super().message_post(message_type=message_type, **kwargs)
        if (
            self.channel_type == "livechat"
            and self.livechat_channel_id
            and self.livechat_channel_id.whatsapp_gateway_id
            and message.message_type != "notification"
            and not self.env.context.get("no_gateway_notification")
        ):
            gateway = self.livechat_channel_id.whatsapp_gateway_id
            self.env["mail.notification"].create(
                {
                    "mail_message_id": message.id,
                    "gateway_channel_id": self.id,
                    "notification_type": "gateway",
                    "gateway_type": gateway.gateway_type,
                }
            ).send_gateway()
        return message
