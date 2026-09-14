# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class WhatsappComposer(models.TransientModel):
    """Attach the business document PDF to the WhatsApp message."""

    _inherit = "whatsapp.composer"

    def _action_send_whatsapp(self):
        record = self.env[self.res_model].browse(self.res_id)
        if not record:
            return super()._action_send_whatsapp()
        attachments = (
            record._whatsapp_get_attachments()
            if hasattr(record, "_whatsapp_get_attachments")
            else False
        )
        if not attachments:
            return super()._action_send_whatsapp()
        channel = record._whatsapp_get_channel(self.number_field_name, self.gateway_id)
        channel.with_context(
            whatsapp_template_id=self.template_id.id,
            default_res_id=self.res_id,
        ).message_post(
            body=self.body,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
            attachment_ids=attachments.ids,
        )
