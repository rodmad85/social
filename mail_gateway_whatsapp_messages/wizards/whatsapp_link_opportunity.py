from odoo import api, fields, models


class WhatsappLinkOpportunityWizard(models.TransientModel):
    _name = "whatsapp.link.opportunity.wizard"
    _description = "Link WhatsApp Conversation to CRM Opportunity"

    channel_id = fields.Many2one("discuss.channel", string="Channel", required=True)
    partner_id = fields.Many2one("res.partner", string="Contact")
    existing_opportunity_id = fields.Many2one(
        "crm.lead",
        string="Oportunidade Existente",
        domain=[("type", "=", "opportunity")],
    )
    new_opportunity_name = fields.Char(string="Nome da Nova Oportunidade")

    @api.constrains("existing_opportunity_id", "new_opportunity_name")
    def _check_opportunity(self):
        for record in self:
            if not record.existing_opportunity_id and not record.new_opportunity_name:
                raise models.ValidationError(
                    "Selecione uma oportunidade existente ou informe o nome para criar uma nova."
                )

    def action_link(self):
        self.ensure_one()
        if self.existing_opportunity_id:
            opportunity = self.existing_opportunity_id
        else:
            opportunity = self.env["crm.lead"].create({
                "name": self.new_opportunity_name,
                "partner_id": self.partner_id.id if self.partner_id else False,
                "type": "opportunity",
            })
        link = self.env["mail.whatsapp.chatter.link"].get_or_create(
            self.channel_id, opportunity
        )
        current_partner = self.env.user.partner_id
        if not any(
            m.partner_id == current_partner
            for m in self.channel_id.channel_member_ids
        ):
            self.env["discuss.channel.member"].sudo().create({
                "partner_id": current_partner.id,
                "channel_id": self.channel_id.id,
                "is_pinned": False,
                "unpin_dt": False,
            })
        return {
            "type": "ir.actions.act_window_close",
        }
