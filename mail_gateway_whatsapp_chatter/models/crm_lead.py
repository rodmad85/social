from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    whatsapp_channel_id = fields.Many2one(
        "discuss.channel",
        string="WhatsApp",
        compute="_compute_whatsapp_channel_id",
    )

    def _compute_whatsapp_channel_id(self):
        if not self.env.registry.get("mail.whatsapp.chatter.link"):
            self.whatsapp_channel_id = False
            return
        for lead in self:
            link = self.env["mail.whatsapp.chatter.link"].search(
                [("res_model", "=", "crm.lead"), ("res_id", "=", lead.id)], limit=1
            )
            lead.whatsapp_channel_id = link.channel_id if link else False

    def action_claim_whatsapp_conversation(self):
        self.ensure_one()
        channel = self.whatsapp_channel_id
        if not channel:
            return
        current_partner = self.env.user.partner_id
        if not any(
            member.partner_id == current_partner
            for member in channel.channel_member_ids
        ):
            self.env["discuss.channel.member"].sudo().create(
                {
                    "partner_id": current_partner.id,
                    "channel_id": channel.id,
                    "is_pinned": False,
                    "unpin_dt": False,
                }
            )
        return {
            "type": "ir.actions.client",
            "tag": "mail.action_discuss",
            "params": {"active_id": f"discuss.channel_{channel.id}"},
        }
