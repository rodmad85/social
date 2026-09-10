from odoo import api, fields, models


class WhatsappAssignContactWizard(models.TransientModel):
    _name = "whatsapp.assign.contact.wizard"
    _description = "Assign WhatsApp Conversation to a Contact"

    partner_id = fields.Many2one(
        "res.partner", string="Contact", required=True, domain=[("phone", "!=", False)]
    )
    channel_id = fields.Many2one("discuss.channel", string="Channel", required=True)
    phone = fields.Char(string="Phone", readonly=True)

    def action_assign(self):
        partner = self.partner_id
        gateway = self.channel_id.gateway_id
        token = self.channel_id.gateway_channel_token

        partner_phone = partner.phone_sanitized
        incoming_phone = "+" + token if not token.startswith("+") else token
        phone_is_different = partner_phone and incoming_phone and partner_phone != incoming_phone

        if phone_is_different:
            alt = self.env["res.partner.whatsapp.phone"].search([
                ("partner_id", "=", partner.id),
                ("phone_sanitized", "=", incoming_phone),
            ], limit=1)
            if not alt:
                self.env["res.partner.whatsapp.phone"].create({
                    "partner_id": partner.id,
                    "phone": token,
                })

        self.env["res.partner.gateway.channel"]._get_or_create_for_gateway(
            partner, gateway, token
        )

        channel_name = partner.display_name
        self.channel_id.name = channel_name

        if not self.env["discuss.channel.member"].sudo().search_count([
            ("channel_id", "=", self.channel_id.id),
            ("partner_id", "=", partner.id),
        ]):
            self.env["discuss.channel.member"].sudo().create({
                "channel_id": self.channel_id.id,
                "partner_id": partner.id,
                "unpin_dt": False,
            })

        guest = self.env["mail.guest"].search([
            ("gateway_id", "=", gateway.id),
            ("gateway_token", "=", token),
        ], limit=1)
        if guest and not guest.partner_id:
            existing_members = self.env["discuss.channel.member"].sudo().search([
                ("channel_id", "=", self.channel_id.id),
                ("guest_id", "=", guest.id),
            ])
            existing_members.unlink()
            guest.write({"partner_id": partner.id})

        return {"type": "ir.actions.act_window_close"}
