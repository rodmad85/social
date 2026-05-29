from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    is_whatsapp_incoming = fields.Boolean(
        compute="_compute_is_whatsapp_incoming",
        string="Incoming WhatsApp",
    )

    @api.depends("gateway_type", "author_id")
    def _compute_is_whatsapp_incoming(self):
        current_partner = self.env.user.partner_id
        for msg in self:
            if (
                msg.gateway_type == "whatsapp"
                and msg.author_id
                and msg.author_id != current_partner
            ):
                msg.is_whatsapp_incoming = True
            else:
                msg.is_whatsapp_incoming = False

    def _to_store(self, store, /, *, fields=None, **kwargs):
        result = super()._to_store(store, fields=fields, **kwargs)
        for record in self:
            store.add(record, {"gateway_type": record.gateway_type})
            if record.gateway_type == "whatsapp":
                status = False
                notification = record.gateway_notification_ids[:1]
                if notification:
                    status = notification[0].notification_status
                store.add(record, {"whatsapp_notification_status": status})
        return result

    def _send_to_gateway_thread(self, gateway_channel_id):
        result = super()._send_to_gateway_thread(gateway_channel_id)
        chat_id = gateway_channel_id.gateway_id._get_channel_id(
            gateway_channel_id.gateway_token
        )
        channel = self.env["discuss.channel"].browse(chat_id)
        if channel and self.model and self.res_id and gateway_channel_id.gateway_id.gateway_type == "whatsapp":
            record = self.env[self.model].browse(self.res_id)
            if record.exists():
                self.env["mail.whatsapp.chatter.link"].get_or_create(channel, record)
        return result


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _get_gateway_follower_partners(self, record):
        partners = self.env["res.partner"]
        followers = record.message_get_followers()
        if "mail.followers" in followers:
            follower_partner_ids = [
                f["partner"]["id"]
                for f in followers["mail.followers"]
                if isinstance(f.get("partner"), dict)
            ]
            partners |= self.env["res.partner"].browse(set(follower_partner_ids))
        if "partner_id" in record._fields and record.partner_id:
            partners |= record.partner_id
        return partners.filtered("gateway_channel_ids")

    def _thread_to_store(self, store, /, *, fields=None, request_list=None):
        res = super()._thread_to_store(store, fields=fields, request_list=request_list)
        for record in self:
            partners_with_gateway = self._get_gateway_follower_partners(record)
            if partners_with_gateway:
                store.add(
                    record,
                    {
                        "gateway_followers": [
                            {"id": p.id, "type": "partner"}
                            for p in partners_with_gateway
                        ]
                    },
                    as_thread=True,
                )
                for partner in partners_with_gateway:
                    store.add(
                        "res.partner",
                        {
                            "id": partner.id,
                            "gateway_channels": [
                                gc._mail_format()
                                for gc in partner.gateway_channel_ids
                            ],
                        },
                    )
        return res


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _to_store(self, store, /, *, fields=None, main_user_by_partner=None):
        res = super()._to_store(
            store, fields=fields, main_user_by_partner=main_user_by_partner
        )
        partners_with_gateway = self.filtered("gateway_channel_ids")
        for partner in partners_with_gateway:
            store.add(
                "res.partner",
                {
                    "id": partner.id,
                    "gateway_channels": [
                        gc._mail_format() for gc in partner.gateway_channel_ids
                    ],
                },
            )
        return res
