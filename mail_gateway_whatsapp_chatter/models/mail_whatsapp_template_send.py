from odoo import api, fields, models


class MailWhatsAppTemplateSend(models.Model):
    _name = "mail.whatsapp.template.send"
    _description = "WhatsApp Template Send Tracking"
    _order = "send_date desc"

    template_id = fields.Many2one(
        "mail.whatsapp.template",
        required=True,
        ondelete="cascade",
    )
    channel_id = fields.Many2one(
        "discuss.channel",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contato",
        compute="_compute_partner",
        store=True,
    )
    send_date = fields.Datetime(required=True, default=fields.Datetime.now)
    message_id = fields.Many2one("mail.message")
    user_id = fields.Many2one(
        "res.users",
        string="Usuário",
        compute="_compute_user",
        store=True,
    )
    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Oportunidade",
        compute="_compute_opportunity",
        store=True,
    )
    remaining_time = fields.Float(
        string="Tempo Restante (h)",
        compute="_compute_remaining_time",
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("waiting", "Aguardando Resposta"),
            ("responded", "Respondido"),
            ("expired", "Expirado"),
        ],
        string="Estado",
        compute="_compute_state",
        store=True,
    )

    @api.depends("channel_id")
    def _compute_partner(self):
        for record in self:
            record.partner_id = False
            channel = record.channel_id
            if channel.gateway_channel_token and channel.gateway_id:
                gc = self.env["res.partner.gateway.channel"].search([
                    ("gateway_id", "=", channel.gateway_id.id),
                    ("gateway_token", "=", channel.gateway_channel_token),
                ], limit=1)
                if gc:
                    record.partner_id = gc.partner_id

    @api.depends("message_id")
    def _compute_user(self):
        for record in self:
            record.user_id = False
            author = record.message_id.author_id
            if author and author._name == "res.partner" and author.user_ids:
                record.user_id = author.user_ids[0]

    @api.depends("channel_id")
    def _compute_opportunity(self):
        for record in self:
            record.opportunity_id = False
            link = self.env["mail.whatsapp.chatter.link"].search([
                ("channel_id", "=", record.channel_id.id),
                ("res_model", "=", "crm.lead"),
            ], limit=1)
            if link:
                record.opportunity_id = self.env["crm.lead"].browse(link.res_id)

    @api.depends("send_date")
    def _compute_remaining_time(self):
        for record in self:
            if not record.send_date:
                record.remaining_time = 0.0
                continue
            send_dt = fields.Datetime.from_string(record.send_date)
            now = fields.Datetime.from_string(fields.Datetime.now())
            diff_hours = (now - send_dt).total_seconds() / 3600
            remaining = 24 - diff_hours
            if remaining <= 0:
                record.remaining_time = 0.0
            else:
                record.remaining_time = round(remaining, 2)

    @api.depends("send_date", "remaining_time")
    def _compute_state(self):
        for record in self:
            if not record.send_date:
                record.state = "waiting"
                continue
            if record.remaining_time <= 0:
                record.state = "expired"
                continue
            has_response = self.env["mail.message"].search_count([
                ("channel_id", "=", record.channel_id.id),
                ("date", ">", record.send_date),
                ("gateway_type", "=", "whatsapp"),
                ("author_id", "!=", False),
                ("author_id", "!=", self.env.user.partner_id.id),
            ], limit=1)
            if has_response:
                record.state = "responded"
            else:
                record.state = "waiting"