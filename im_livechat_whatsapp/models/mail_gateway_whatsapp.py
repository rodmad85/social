# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _get_channel(self, gateway, token, update, force_create=False):
        """Route incoming WhatsApp messages to livechat channels when the
        gateway is linked to an ``im_livechat.channel``.

        When the gateway has a ``livechat_channel_id``, this method searches
        for an existing livechat channel by ``gateway_channel_token`` and
        creates one if needed, delegating operator selection to the livechat
        channel's ``_get_operator`` method.
        """
        if not gateway.livechat_channel_id:
            return super()._get_channel(
                gateway, token, update, force_create=force_create
            )
        chat_id = gateway._get_channel_id(token)
        if chat_id:
            return self.env["discuss.channel"].browse(chat_id)
        if not force_create and gateway.has_new_channel_security:
            return False
        vals = self.env["discuss.channel"]._get_livechat_whatsapp_channel_vals(
            gateway, token, update
        )
        if not vals:
            return False
        channel = self.env["discuss.channel"].create(vals)
        channel._broadcast(channel.channel_member_ids.mapped("partner_id").ids)
        return channel
