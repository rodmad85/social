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
                if (
                    record.exists()
                    and "user_id" in record._fields
                    and record.user_id
                    and record.user_id != self.env.user
                    and not self.env.user.has_group("sales_team.group_sale_manager")
                    and not self.env.user.has_group("crm_commissions.group_crm_commission_sdr")
                ):
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
        if channel and gateway_channel_id.gateway_id.gateway_type == "whatsapp":
            if not self.env["discuss.channel.member"].sudo().search_count([
                ("channel_id", "=", channel.id),
                ("partner_id", "=", self.env.user.partner_id.id),
            ]):
                self.env["discuss.channel.member"].sudo().create({
                    "channel_id": channel.id,
                    "partner_id": self.env.user.partner_id.id,
                })
            if self.model and self.res_id:
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

    def _get_gateway_follower_partners(self, record, allow_phone=False):
        partners = self.env["res.partner"]
        if "partner_id" in record._fields and record.partner_id:
            partners |= record.partner_id
        if not allow_phone:
            partners = partners.filtered("gateway_channel_ids")
        return partners

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
                old_channel = self.env["discuss.channel"].search([
                    ("gateway_channel_token", "=", existing.gateway_token),
                    ("gateway_id", "=", gateway.id),
                ], limit=1)
                if old_channel:
                    old_channel.gateway_channel_token = sanitized_number
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
            gateway_followers = self._get_gateway_follower_partners(
                record, allow_phone=True
            )
            whatsapp_can_send = not (
                "user_id" in record._fields
                and record.user_id
                and record.user_id != self.env.user
            )
            link = self.env["mail.whatsapp.chatter.link"].sudo().search([
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ], limit=1)
            has_whatsapp_conversation = bool(
                link
                and link.channel_id
                and link.channel_id.message_ids.filtered(
                    lambda m: m.gateway_type == "whatsapp"
                )
            )
            store.add(
                record,
                {
                    "gateway_followers": [
                        {"id": p.id, "type": "partner"}
                        for p in gateway_followers
                    ],
                    "whatsapp_can_send": whatsapp_can_send,
                    "has_whatsapp_conversation": has_whatsapp_conversation,
                },
                as_thread=True,
            )
            for partner in gateway_followers:
                gateway_channels = partner.gateway_channel_ids
                store.add(
                    "res.partner",
                    {
                        "id": partner.id,
                        "gateway_channels": [
                            gc._mail_format() for gc in gateway_channels
                        ]
                        if gateway_channels
                        else [],
                    },
                )
        return res


class MailMessageGatewayLink(models.TransientModel):
    _inherit = "mail.message.gateway.link"

    @api.model
    def _selection_target_model(self):
        models = self.env["ir.model"].sudo().search([("is_mail_thread", "=", True)])
        return [(model.model, model.name) for model in models]


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


class WhatsappComposer(models.TransientModel):
    _inherit = "whatsapp.composer"

    def _action_send_whatsapp(self):
        record = self.env[self.res_model].browse(self.res_id)
        if not record:
            return
        channel = record._whatsapp_get_channel(
            self.number_field_name, self.gateway_id
        )
        self.env["mail.whatsapp.chatter.link"].get_or_create(channel, record)
        channel.with_context(
            whatsapp_template_id=self.template_id.id
        ).message_post(
            body=self.body,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
        )
