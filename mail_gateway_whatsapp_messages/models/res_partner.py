from odoo import api, fields, models


class ResPartnerWhatsappPhone(models.Model):
    _name = "res.partner.whatsapp.phone"
    _description = "Additional WhatsApp phone numbers for a partner"

    partner_id = fields.Many2one(
        "res.partner", string="Contact", required=True, ondelete="cascade"
    )
    phone = fields.Char(string="Phone", required=True)
    phone_sanitized = fields.Char(string="Phone Sanitized", compute="_compute_phone_sanitized", store=True)
    description = fields.Char(string="Description", help="e.g. Office, Spare phone")

    _sql_constraints = [
        (
            "unique_partner_phone",
            "UNIQUE(partner_id, phone)",
            "This phone is already registered for this contact.",
        ),
    ]

    @api.depends("phone")
    def _compute_phone_sanitized(self):
        for record in self:
            phone = record.phone or ""
            sanitized = "".join(c for c in phone if c.isdigit())
            if sanitized and not sanitized.startswith("+"):
                sanitized = "+" + sanitized
            record.phone_sanitized = sanitized


class ResPartner(models.Model):
    _inherit = "res.partner"

    whatsapp_phone_ids = fields.One2many(
        "res.partner.whatsapp.phone", "partner_id", string="WhatsApp Phones"
    )
