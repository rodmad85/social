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
            existing_tokens = set(
                gc.gateway_token for gc in partner.gateway_channel_ids
            )
            for wp in partner.whatsapp_phone_ids:
                sanitized = "".join(c for c in wp.phone if c.isdigit())
                if sanitized in existing_tokens:
                    continue
                self.env["res.partner.gateway.channel"].sudo().create({
                    "partner_id": partner.id,
                    "gateway_id": gateway.id,
                    "gateway_token": sanitized,
                })
                existing_tokens.add(sanitized)
            partner.invalidate_recordset(["gateway_channel_ids"])
        return partners
