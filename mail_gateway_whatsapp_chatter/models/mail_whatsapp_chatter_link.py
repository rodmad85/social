from odoo import api, fields, models


class MailWhatsappChatterLink(models.Model):
    _name = "mail.whatsapp.chatter.link"
    _description = "Link between a discuss channel and a business record"
    _rec_name = "display_name"

    channel_id = fields.Many2one("discuss.channel", required=True, ondelete="cascade")
    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    partner_id = fields.Many2one("res.partner")
    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("channel_id", "res_model", "res_id")
    def _compute_display_name(self):
        for link in self:
            record = self.env[link.res_model].browse(link.res_id)
            link.display_name = (
                f"{link.channel_id.name} - {record.display_name}"
                if record
                else link.channel_id.name
            )

    _sql_constraints = [
        (
            "unique_channel_thread",
            "UNIQUE(channel_id, res_model, res_id)",
            "A channel can only be linked once to the same thread.",
        ),
    ]

    @api.model
    def get_or_create(self, channel, record):
        link = self.search(
            [
                ("channel_id", "=", channel.id),
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ],
            limit=1,
        )
        if not link:
            partner = record if record._name == "res.partner" else getattr(record, "partner_id", False)
            link = self.create(
                {
                    "channel_id": channel.id,
                    "res_model": record._name,
                    "res_id": record.id,
                    "partner_id": partner.id if partner else False,
                }
            )
        return link
