from odoo import models


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _post_to_linked_threads(self, body, attachment_ids, author, chat):
        links = self.env["mail.whatsapp.chatter.link"].search(
            [("channel_id", "=", chat.id)]
        )
        for link in links:
            record = self.env[link.res_model].browse(link.res_id)
            if not record.exists():
                continue
            author_id = author.id if author and author._name == "res.partner" else False
            record.message_post(
                body=body,
                author_id=author_id,
                gateway_type="whatsapp",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                attachment_ids=attachment_ids,
            )

    def _post_process_message(self, message, channel):
        result = super()._post_process_message(message, channel)
        if channel.gateway_id and channel.gateway_id.gateway_type == "whatsapp":
            author = message.author_id
            self._post_to_linked_threads(
                message.body, message.attachment_ids.ids, author, channel
            )
        return result
