from odoo import models


class MailThread(models.Model):
    _inherit = 'mail.thread'

    def action_send_whatsapp(self, message):
        """Action to send message via WhatsApp (called from JS)."""
        # Placeholder for WhatsApp send logic
        # Integrate with WhatsApp Business API here
        self.message_post(
            body=message,
            message_type='whatsapp',
            subtype_xmlid='mail.mt_whatsapp',
        )
