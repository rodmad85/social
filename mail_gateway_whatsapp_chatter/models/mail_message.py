from odoo import Command, api, fields, models
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
        if gateway_channel_id.gateway_id.gateway_type != "whatsapp":
            return super()._send_to_gateway_thread(gateway_channel_id)
        gateway = gateway_channel_id.gateway_id
        partner = gateway_channel_id.partner_id
        service = self.env["mail.gateway.whatsapp"]
        update = {
            "contacts": [{
                "wa_id": gateway_channel_id.gateway_token,
                "profile": {"name": partner.display_name},
            }],
            "messages": [{"from": gateway_channel_id.gateway_token}],
        }
        channel = service._get_channel(
            gateway, gateway_channel_id.gateway_token, update, force_create=True
        )
        if not channel:
            return super()._send_to_gateway_thread(gateway_channel_id)
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
            self.env["mail.whatsapp.chatter.link"].get_or_create(channel, record)
        if not self.env["discuss.channel.member"].sudo().search_count([
            ("channel_id", "=", channel.id),
            ("partner_id", "=", self.env.user.partner_id.id),
        ]):
            self.env["discuss.channel.member"].sudo().create({
                "channel_id": channel.id,
                "partner_id": self.env.user.partner_id.id,
            })
        posted_message = channel.message_post(**self._get_gateway_thread_message_vals())
        if not self.gateway_type:
            self.gateway_type = gateway_channel_id.gateway_id.gateway_type
        notification_vals = {
            "notification_status": "sent",
            "mail_message_id": self.id,
            "gateway_channel_id": channel.id,
            "notification_type": "gateway",
            "gateway_type": gateway_channel_id.gateway_id.gateway_type,
        }
        channel_notif = self.env["mail.notification"].search([
            ("mail_message_id", "=", posted_message.id),
            ("notification_type", "=", "gateway"),
        ], limit=1)
        if channel_notif:
            notification_vals["gateway_message_id"] = channel_notif.gateway_message_id
            if channel_notif.failure_type == "unknown":
                notification_vals["failure_type"] = "unknown"
                notification_vals["notification_status"] = "exception"
                notification_vals["failure_reason"] = channel_notif.failure_reason
        self.env["mail.notification"].create(notification_vals)
        return {}

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
        if allow_phone:
            return partners.filtered(
                lambda p: p.gateway_channel_ids or p.mobile or p.phone
            )
        return partners.filtered("gateway_channel_ids")

    def _whatsapp_get_or_create_channel(self, gateway, sanitized_number, partner):
        chat_id = gateway._get_channel_id(sanitized_number)
        if chat_id:
            channel = self.env["discuss.channel"].browse(chat_id)
            if partner and channel.name != partner.display_name:
                channel.name = partner.display_name
            return channel
        members = [
            Command.create({"partner_id": p.id, "unpin_dt": False})
            for p in gateway.member_ids.partner_id
        ]
        members.append(
            Command.create({"partner_id": partner.id})
        )
        channel = self.env["discuss.channel"].create({
            "gateway_channel_token": sanitized_number,
            "gateway_id": gateway.id,
            "channel_type": "gateway",
            "channel_member_ids": members,
            "company_id": gateway.company_id.id,
            "name": partner.display_name,
        })
        channel._broadcast(channel.channel_member_ids.mapped("partner_id").ids)
        return channel

    def _whatsapp_get_channel(self, field_name, gateway):
        sanitized_number = self._phone_format(number=self[field_name])
        if not sanitized_number:
            raise UserError(self.env._("Phone cannot be sanitized"))
        sanitized_number = sanitized_number.replace("+", "")
        partner = self._whatsapp_get_partner()
        if partner:
            self.env["res.partner.gateway.channel"]._get_or_create_for_gateway(
                partner, gateway, sanitized_number
            )
        return self._whatsapp_get_or_create_channel(
            gateway, sanitized_number, partner
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
                gateway = (
                    self.env["mail.gateway"]
                    .sudo()
                    .search(
                        [("gateway_type", "=", "whatsapp")], limit=1
                    )
                )
                if gateway:
                    phone = partner.mobile or partner.phone
                    if phone:
                        sanitized_phone = self._phone_format(number=phone)
                        sanitized = sanitized_phone.replace("+", "") if sanitized_phone else "".join(c for c in phone if c.isdigit())
                        self.env["res.partner.gateway.channel"].sudo()._get_or_create_for_gateway(
                            partner, gateway, sanitized
                        )
                partner = self.env["res.partner"].browse(partner.id)
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


class ResPartnerGatewayChannel(models.Model):
    _inherit = "res.partner.gateway.channel"

    def _get_or_create_for_gateway(self, partner, gateway, gateway_token):
        gateway_channel_model = self.browse([])
        gateway_channel = gateway_channel_model.search(
            [
                ("partner_id", "=", partner.id),
                ("gateway_id", "=", gateway.id),
            ],
            limit=1,
        )
        if gateway_channel:
            if gateway_channel.gateway_token != gateway_token:
                gateway_channel.gateway_token = gateway_token
            return gateway_channel
        return gateway_channel_model.create(
            {
                "partner_id": partner.id,
                "gateway_id": gateway.id,
                "gateway_token": gateway_token,
            }
        )

    def _mail_format(self):
        res = super()._mail_format()
        partner = self.partner_id
        token = (self.gateway_token or "").replace("+", "")
        is_mobile = False
        if partner:
            if partner.mobile:
                mobile_digits = "".join(c for c in partner.mobile if c.isdigit())
                if token and token == mobile_digits:
                    res["name"] = "Mobile: %s" % partner.mobile
                    is_mobile = True
            if not is_mobile and partner.phone:
                phone_digits = "".join(c for c in partner.phone if c.isdigit())
                if token and token == phone_digits:
                    res["name"] = "Phone: %s" % partner.phone
            if not is_mobile:
                for wp in partner.whatsapp_phone_ids:
                    wp_digits = "".join(c for c in (wp.phone or "") if c.isdigit())
                    if token and token == wp_digits:
                        if wp.description:
                            res["name"] = "%s (%s)" % (wp.phone, wp.description)
                        else:
                            res["name"] = wp.phone
                        break
            if not is_mobile and token:
                res["name"] = token
        elif token:
            res["name"] = token
        res["is_mobile"] = is_mobile
        return res


class WhatsappComposer(models.TransientModel):
    _inherit = "whatsapp.composer"

    phone_number = fields.Selection(
        selection="_selection_phone_number",
        string="Phone Number",
    )
    has_multiple_phones = fields.Boolean(
        compute="_compute_has_multiple_phones",
    )

    @api.depends("res_model", "res_id")
    def _compute_has_multiple_phones(self):
        for wizard in self:
            options = wizard._selection_phone_number()
            wizard.has_multiple_phones = len(options) > 1

    def _selection_phone_number(self):
        if not self or not self.res_model or not self.res_id:
            return [("mobile", "Mobile"), ("phone", "Phone")]
        record = self.env[self.res_model].browse(self.res_id)
        partner = record if record._name == "res.partner" else record.partner_id
        if not partner:
            return [("mobile", "Mobile"), ("phone", "Phone")]
        options = []
        if partner.mobile:
            options.append(("mobile", "Mobile: %s" % partner.mobile))
        if partner.phone:
            options.append(("phone", "Phone: %s" % partner.phone))
        for wp in partner.whatsapp_phone_ids:
            label = "%s (%s)" % (wp.phone, wp.description) if wp.description else wp.phone
            options.append(("whatsapp_%d" % wp.id, label))
        return options or [("mobile", "Mobile"), ("phone", "Phone")]

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if "phone_number" in fields or "has_multiple_phones" in fields:
            res_model = res.get("res_model")
            res_id = res.get("res_id")
            if res_model and res_id:
                record = self.env[res_model].browse(res_id)
                partner = record if record._name == "res.partner" else record.partner_id
                if partner:
                    phones = []
                    if partner.mobile:
                        phones.append("mobile")
                    if partner.phone:
                        phones.append("phone")
                    for wp in partner.whatsapp_phone_ids:
                        phones.append("whatsapp_%d" % wp.id)
                    default_number = res.get("number_field_name") or "mobile"
                    if default_number in phones:
                        res["phone_number"] = default_number
                    elif phones:
                        res["phone_number"] = phones[0]
                    res["has_multiple_phones"] = len(phones) > 1
        return res

    def _action_send_whatsapp(self):
        record = self.env[self.res_model].browse(self.res_id)
        if not record:
            return
        phone = self.phone_number or self.number_field_name or "mobile"
        if phone.startswith("whatsapp_"):
            wp_id = int(phone.split("_")[1])
            wp = self.env["res.partner.whatsapp.phone"].browse(wp_id)
            sanitized_number = (wp.phone_sanitized or wp.phone).replace("+", "")
            partner = record._whatsapp_get_partner()
            gateway = self.gateway_id
            self.env["res.partner.gateway.channel"]._get_or_create_for_gateway(
                partner, gateway, sanitized_number
            )
            channel = self.env["mail.gateway.whatsapp"]._get_channel(
                gateway, sanitized_number, {
                    "contacts": [{"wa_id": sanitized_number, "profile": {"name": partner.display_name}}],
                    "messages": [{"from": sanitized_number}],
                }, force_create=True,
            )
        else:
            channel = record._whatsapp_get_channel(phone, self.gateway_id)
        self.env["mail.whatsapp.chatter.link"].get_or_create(channel, record)
        if not self.env["discuss.channel.member"].sudo().search_count([
            ("channel_id", "=", channel.id),
            ("partner_id", "=", self.env.user.partner_id.id),
        ]):
            self.env["discuss.channel.member"].sudo().create({
                "channel_id": channel.id,
                "partner_id": self.env.user.partner_id.id,
            })
        channel.with_context(
            whatsapp_template_id=self.template_id.id
        ).message_post(
            body=self.body,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
        )
