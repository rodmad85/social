# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import Command, api, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _get_whatsapp_livechat_channel(self, gateway):
        """Return the ``im_livechat.channel`` linked to ``gateway`` if any."""
        return self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", gateway.id)], limit=1
        )

    def _get_whatsapp_gateway_channel(self):
        """Return the gateway (bot) channel paired to this conversation
        channel for the same WhatsApp phone number."""
        if not self.gateway_channel_token or not self.livechat_channel_id:
            return self.env["discuss.channel"]
        gateway = self.livechat_channel_id.whatsapp_gateway_id
        if not gateway:
            return self.env["discuss.channel"]
        return self.search(
            [
                ("channel_type", "=", "gateway"),
                ("gateway_id", "=", gateway.id),
                ("gateway_channel_token", "=", self.gateway_channel_token),
            ],
            limit=1,
        )

    @api.model
    def _get_livechat_whatsapp_channel_vals(self, gateway, token, update):
        """Build channel vals for the livechat conversation channel paired to
        a WhatsApp gateway.

        The gateway (bot) channel is created by the base ``mail_gateway``
        module with ``channel_type='gateway'``. This method builds the
        ``channel_type='livechat'`` conversation channel where operators
        answer. It does NOT set ``gateway_id`` so that the automatic send
        handled by ``mail_gateway`` never fires on this channel: outbound
        messages are routed to the paired gateway channel instead.
        """
        livechat_channel = self._get_whatsapp_livechat_channel(gateway)
        if not livechat_channel:
            return {}
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
        member_partner_ids = set(gateway.member_ids.partner_id.ids)
        member_partner_ids.add(user_operator.partner_id.id)
        member_cmds = [
            Command.create({"partner_id": partner_id, "unpin_dt": False})
            for partner_id in member_partner_ids
        ]
        if author:
            if author._name == "res.partner":
                if author.id not in member_partner_ids:
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
            "anonymous_name": name,
            "channel_member_ids": member_cmds,
            "company_id": gateway.company_id.id or False,
        }

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, *, message_type="notification", **kwargs):
        """Route messages on WhatsApp-related livechat channels.

        - On a ``livechat`` channel linked to a WhatsApp gateway, outbound
          messages create a single gateway notification pointing to the paired
          gateway (bot) channel, so they are sent through WhatsApp. A copy is
          mirrored to the gateway channel so gateway administrators see the
          full thread.
        - On a ``gateway`` channel linked to a WhatsApp livechat channel,
          messages are forwarded normally. Duplicate prevention is handled by
          the ``no_gateway_notification`` context flag already set by callers
          that should not trigger sends (webhook inbound, mirrored replies).
        """
        is_livechat_whatsapp = (
            self.channel_type == "livechat"
            and self.livechat_channel_id
            and self.livechat_channel_id.whatsapp_gateway_id
        )
        if is_livechat_whatsapp:
            message = super().message_post(message_type=message_type, **kwargs)
            if (
                message.message_type != "notification"
                and not self.env.context.get("no_gateway_notification")
            ):
                gateway = self.livechat_channel_id.whatsapp_gateway_id
                gateway_channel = self.sudo()._get_whatsapp_gateway_channel()
                if gateway_channel:
                    self.env["mail.notification"].sudo().create(
                        {
                            "mail_message_id": message.id,
                            "gateway_channel_id": gateway_channel.id,
                            "notification_type": "gateway",
                            "gateway_type": gateway.gateway_type,
                        }
                    ).send_gateway()
                    gateway_channel.sudo().with_context(
                        no_gateway_notification=True
                    ).message_post(
                        body=message.body,
                        attachment_ids=message.attachment_ids.ids,
                        subtype_xmlid=message.subtype_id.xml_id,
                        author_id=message.author_id.id,
                        message_type="comment",
                    )
            return message
        return super().message_post(message_type=message_type, **kwargs)