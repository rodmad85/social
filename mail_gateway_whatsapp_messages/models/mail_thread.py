from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _get_gateway_follower_partners(self, record, allow_phone=False):
        partners = super()._get_gateway_follower_partners(
            record, allow_phone=allow_phone
        )
        if not self.env.get("res.partner.whatsapp.phone"):
            return partners
        gateway = (
            self.env["mail.gateway"]
            .sudo()
            .search([("gateway_type", "=", "whatsapp")], limit=1)
        )
        if not gateway:
            return partners
        wpp_partners = partners.filtered("whatsapp_phone_ids")
        for partner in wpp_partners:
            for wp in partner.whatsapp_phone_ids:
                sanitized = "".join(c for c in wp.phone if c.isdigit())
                if sanitized:
                    self.env["res.partner.gateway.channel"].sudo()._get_or_create_for_gateway(
                        partner, gateway, sanitized
                    )
            partner.invalidate_recordset(["gateway_channel_ids"])
        return partners
