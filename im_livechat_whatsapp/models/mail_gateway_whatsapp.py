# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _process_update(self, chat, message, value):
        """Mirror inbound gateway messages into the linked livechat channel.

        The base implementation posts the webhook message on the gateway (bot)
        channel. When the gateway is linked to an ``im_livechat.channel``, the
        message is mirrored into the livechat conversation channel where the
        operator answers, reusing the existing conversation by
        ``gateway_channel_token``.
        """
        super()._process_update(chat, message, value)
        livechat_channel = self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", chat.gateway_id.id)], limit=1
        )
        if not livechat_channel:
            return
        posted = self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", chat.id),
                ("message_type", "=", "comment"),
            ],
            order="id desc",
            limit=1,
        )
        if not posted:
            return
        conversation = self.env["discuss.channel"].search(
            [
                ("channel_type", "=", "livechat"),
                ("livechat_channel_id", "=", livechat_channel.id),
                ("gateway_channel_token", "=", chat.gateway_channel_token),
            ],
            limit=1,
        )
        if not conversation:
            vals = self.env["discuss.channel"]._get_livechat_whatsapp_channel_vals(
                chat.gateway_id, chat.gateway_channel_token, value
            )
            if not vals:
                return
            conversation = self.env["discuss.channel"].create(vals)
            conversation._broadcast(
                conversation.channel_member_ids.mapped("partner_id").ids
            )
        author = self._get_author(chat.gateway_id, value)
        if author and author._name == "mail.guest":
            conversation = conversation.with_user(
                self.env.ref("base.public_user").id
            ).with_context(guest=author)
        conversation.sudo().with_context(no_gateway_notification=True).message_post(
            body=posted.body,
            author_id=author and author._name == "res.partner" and author.id,
            date=posted.date,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
            attachment_ids=posted.attachment_ids.ids,
        )
