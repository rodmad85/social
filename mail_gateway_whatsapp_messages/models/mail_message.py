from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    whatsapp_author_name = fields.Char(
        compute="_compute_whatsapp_author_name",
        string="Autor",
    )

    @api.depends("author_id", "author_guest_id", "gateway_type")
    def _compute_whatsapp_author_name(self):
        for msg in self:
            if msg.gateway_type != "whatsapp":
                msg.whatsapp_author_name = False
            elif msg.author_id:
                msg.whatsapp_author_name = msg.author_id.name
            elif msg.author_guest_id:
                msg.whatsapp_author_name = msg.author_guest_id.name
            else:
                msg.whatsapp_author_name = "Desconhecido"

    @api.depends("gateway_type", "author_id", "author_guest_id")
    def _compute_is_whatsapp_incoming(self):
        current_partner = self.env.user.partner_id
        for msg in self:
            if msg.gateway_type == "whatsapp":
                if msg.author_id and msg.author_id != current_partner:
                    msg.is_whatsapp_incoming = True
                elif msg.author_guest_id and not msg.author_id:
                    msg.is_whatsapp_incoming = True
                else:
                    msg.is_whatsapp_incoming = False
            else:
                msg.is_whatsapp_incoming = False
