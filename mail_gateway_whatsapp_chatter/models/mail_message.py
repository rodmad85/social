from odoo import api, fields, models
from odoo.exceptions import UserError


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
        if gateway_channel_id.gateway_id.gateway_type == "whatsapp":
            chat_id = gateway_channel_id.gateway_id._get_channel_id(
                gateway_channel_id.gateway_token
            )
            if not chat_id:
                token = gateway_channel_id.gateway_token
                self.env["mail.gateway.whatsapp"]._get_channel(
                    gateway_channel_id.gateway_id,
                    token,
                    {
                        "contacts": [
                            {
                                "wa_id": token,
                                "profile": {"name": gateway_channel_id.partner_id.name or token},
                            }
                        ],
                        "messages": [{"from": token}],
                    },
                    force_create=True,
                )
            if self.model and self.res_id:
                record = self.env[self.model].browse(self.res_id)
                if record.exists() and "user_id" in record._fields and record.user_id and record.user_id != self.env.user:
                    raise UserError(
                        self.env._(
                            "Only the assigned salesperson can send WhatsApp messages for this record."
                        )
                    )
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

    def _get_gateway_thread_message_vals(self):
        vals = super()._get_gateway_thread_message_vals()
        if self.env.context.get("whatsapp_template_id"):
            vals["whatsapp_template_id"] = self.env.context["whatsapp_template_id"]
        return vals


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _get_gateway_follower_partners(self, record):
        partners = self.env["res.partner"]
        if "partner_id" in record._fields and record.partner_id:
            partners |= record.partner_id
        return partners.filtered("gateway_channel_ids")

    def _whatsapp_get_channel(self, field_name, gateway):
        sanitized_number = self._phone_format(number=self[field_name])
        if not sanitized_number:
            raise UserError(self.env._("Phone cannot be sanitized"))
        sanitized_number = sanitized_number.replace("+", "")
        partner = self._whatsapp_get_partner()
        existing = self.env["res.partner.gateway.channel"].search(
            [
                ("partner_id", "=", partner.id),
                ("gateway_id", "=", gateway.id),
            ],
            limit=1,
        )
        if existing:
            if existing.gateway_token != sanitized_number:
                existing.gateway_token = sanitized_number
        else:
            self.env["res.partner.gateway.channel"].create(
                {
                    "name": gateway.name,
                    "partner_id": partner.id,
                    "gateway_id": gateway.id,
                    "gateway_token": sanitized_number,
                }
            )
        return self.env["mail.gateway.whatsapp"]._get_channel(
            gateway,
            sanitized_number,
            {
                "contacts": [
                    {
                        "wa_id": sanitized_number,
                        "profile": {"name": partner.display_name},
                    }
                ],
                "messages": [{"from": sanitized_number}],
            },
            force_create=True,
        )

    def _notify_thread_by_gateway(self, message, partners_data, **kwargs):
        gateway_notifications = kwargs.get("gateway_notifications", [])
        for notif in gateway_notifications:
            if notif.get("whatsapp_template_id"):
                message = message.with_context(
                    whatsapp_template_id=notif["whatsapp_template_id"]
                )
                break
        return super()._notify_thread_by_gateway(message, partners_data, **kwargs)

    def _thread_to_store(self, store, /, *, fields=None, request_list=None):
        res = super()._thread_to_store(store, fields=fields, request_list=request_list)
        for record in self:
            partners_with_gateway = self._get_gateway_follower_partners(record)
            if partners_with_gateway:
                whatsapp_can_send = not (
                    "user_id" in record._fields
                    and record.user_id
                    and record.user_id != self.env.user
                )
                store.add(
                    record,
                    {
                        "gateway_followers": [
                            {"id": p.id, "type": "partner"}
                            for p in partners_with_gateway
                        ],
                        "whatsapp_can_send": whatsapp_can_send,
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
