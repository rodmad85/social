from odoo import models


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _get_message_body(self, record):
        body = super()._get_message_body(record)
        author = record.mail_message_id.author_id
        if author and body:
            body = f"*{author.name}*\n\n{body}"
        return body
