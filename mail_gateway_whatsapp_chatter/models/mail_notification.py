from odoo import fields, models


class MailNotification(models.Model):
    _inherit = "mail.notification"

    whatsapp_template_id = fields.Many2one("mail.whatsapp.template")

    def send_gateway(self, auto_commit=False, raise_exception=False, parse_mode="HTML"):
        for record in self:
            ctx_template_id = self.env.context.get("whatsapp_template_id")
            if ctx_template_id and not record.whatsapp_template_id:
                record.sudo().whatsapp_template_id = ctx_template_id
            if record.whatsapp_template_id and not ctx_template_id:
                record = record.with_context(
                    whatsapp_template_id=record.whatsapp_template_id.id
                )
        return super().send_gateway(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            parse_mode=parse_mode,
        )
