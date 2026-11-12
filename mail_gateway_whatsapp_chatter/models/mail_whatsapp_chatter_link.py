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
            self._sync_historical_messages(channel, record)
        return link

    @api.model
    def _sync_historical_messages(self, channel, record):
        current_partner = self.env.user.partner_id
        messages = channel.message_ids.filtered(
            lambda m: m.gateway_type == "whatsapp"
            and m.author_id
            and m.author_id != current_partner
        ).sorted(key=lambda m: m.id)
        if not messages:
            return
        for message in messages:
            author_id = message.author_id.id if message.author_id and message.author_id._name == "res.partner" else False
            record.sudo().message_post(
                body=message.body,
                author_id=author_id,
                gateway_type="whatsapp",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                attachment_ids=message.attachment_ids.ids,
            )
