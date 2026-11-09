# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _process_update(self, chat, message, value):
        """Mirror inbound gateway messages into the linked livechat channel."""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("DEBUG _process_update: called for chat %s (type=%s)", chat.id, chat.channel_type)
        
        super()._process_update(chat, message, value)
        _logger.info("DEBUG _process_update: super() completed")
        
        livechat_channel = self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", chat.gateway_id.id)], limit=1
        )
        _logger.info("DEBUG _process_update: livechat_channel found=%s", livechat_channel.id if livechat_channel else False)
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
        _logger.info("DEBUG _process_update: posted message found=%s", posted.id if posted else False)
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
        _logger.info("DEBUG _process_update: existing conversation=%s", conversation.id if conversation else False)
        if not conversation:
            _logger.info("DEBUG _process_update: calling _get_livechat_whatsapp_channel_vals for gateway=%s token=%s", chat.gateway_id.id, chat.gateway_channel_token)
            vals = self.env["discuss.channel"]._get_livechat_whatsapp_channel_vals(
                chat.gateway_id, chat.gateway_channel_token, value
            )
            _logger.info("DEBUG _process_update: vals returned=%s", bool(vals))
            if not vals:
                _logger.warning("DEBUG _process_update: vals is empty, returning")
                return
            _logger.info("DEBUG _process_update: creating conversation")
            conversation = self.env["discuss.channel"].create(vals)
            _logger.info("DEBUG _process_update: conversation created=%s", conversation.id)
            conversation._broadcast(
                conversation.channel_member_ids.mapped("partner_id").ids
            )
        author = self._get_author(chat.gateway_id, value)
        if author and author._name == "mail.guest":
            conversation = conversation.with_user(
                self.env.ref("base.public_user").id
            ).with_context(guest=author)
        _logger.info("DEBUG _process_update: posting message to conversation=%s", conversation.id)
        conversation.sudo().with_context(no_gateway_notification=True).message_post(
            body=posted.body,
            author_id=author and author._name == "res.partner" and author.id,
            date=posted.date,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
            attachment_ids=posted.attachment_ids.ids,
        )
        _logger.info("DEBUG _process_update: message posted to conversation %s", conversation.id)
