from odoo import api, models
from odoo.exceptions import UserError


class IrServerAction(models.Model):
    _inherit = "ir.actions.server"

    @api.depends("state")
    def _compute_available_model_ids(self):
        gateway_based = self.filtered(lambda action: action.state == "whatsapp")
        if gateway_based:
            mail_models = (
                self.env["ir.model"]
                .sudo()
                .search([("is_mail_thread", "=", True), ("transient", "=", False)])
            )
            gateway_based.available_model_ids = mail_models.ids
        return super(
            IrServerAction, self - gateway_based
        )._compute_available_model_ids()


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _send(
        self,
        gateway,
        record,
        auto_commit=False,
        raise_exception=False,
        parse_mode=False,
    ):
        channel = record.gateway_channel_id
        if (
            channel
            and channel.gateway_id
            and channel.gateway_id.gateway_type == "whatsapp"
        ):
            link = self.env["mail.whatsapp.chatter.link"].search(
                [("channel_id", "=", channel.id)], limit=1
            )
            if link:
                record_model = self.env[link.res_model].browse(link.res_id)
                if (
                    record_model.exists()
                    and "user_id" in record_model._fields
                    and record_model.user_id
                    and record_model.user_id != self.env.user
                    and not self.env.user.has_group("sales_team.group_sale_manager")
                    and not self.env.user.has_group(
                        "crm_commissions.group_crm_commission_sdr"
                    )
                ):
                    raise UserError(
                        self.env._(
                            "Only the assigned salesperson can send WhatsApp messages for this record."
                        )
                    )
        return super()._send(
            gateway,
            record,
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            parse_mode=parse_mode,
        )

    def _post_to_linked_threads(self, body, attachment_ids, author, chat):
        links = self.env["mail.whatsapp.chatter.link"].search(
            [("channel_id", "=", chat.id)]
        )
        for link in links:
            record = self.env[link.res_model].browse(link.res_id)
            if not record.exists():
                continue
            author_id = author.id if author and author._name == "res.partner" else False
            message = record.sudo().message_post(
                body=body,
                author_id=author_id,
                gateway_type="whatsapp",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                attachment_ids=attachment_ids,
            )
            if message:
                partners = record.message_follower_ids.partner_id
                active_users = self.env["res.users"].search(
                    [
                        ("partner_id", "in", partners.ids),
                        ("active", "=", True),
                    ]
                )
                for user in active_users:
                    user._bus_send_store(
                        message.with_user(user).with_context(allowed_company_ids=[]),
                        notification_type="mail.record/insert",
                    )

    def _get_author(self, gateway, update):
        messages = update.get("messages")
        if not messages:
            return False
        author_id = messages[0].get("from")
        if author_id:
            gateway_partner = self.env["res.partner.gateway.channel"].search(
                [
                    ("gateway_id", "=", gateway.id),
                    ("gateway_token", "=", str(author_id)),
                ],
                limit=1,
            )
            if gateway_partner:
                return gateway_partner.partner_id
            partner = self.env["res.partner"].search(
                [("phone_sanitized", "=", "+" + str(author_id))], limit=1
            )
            if not partner:
                partner = self.env["res.partner"].search(
                    [("phone_sanitized", "=", str(author_id))], limit=1
                )
            if not partner:
                candidates = [str(author_id)]
                if len(str(author_id)) == 12:
                    candidates.append(str(author_id)[:4] + "9" + str(author_id)[4:])
                elif len(str(author_id)) == 13:
                    candidates.append(str(author_id)[:4] + str(author_id)[5:])
                for candidate in candidates:
                    partner = self.env["res.partner"].search(
                        [
                            ("phone_sanitized", "=like", "%" + candidate[-8:]),
                        ],
                        limit=1,
                    )
                    if partner:
                        break
            if partner:
                self.env["res.partner.gateway.channel"]._get_or_create_for_gateway(
                    partner, gateway, str(author_id)
                )
                return partner
            guest = self.env["mail.guest"].search(
                [
                    ("gateway_id", "=", gateway.id),
                    ("gateway_token", "=", str(author_id)),
                ]
            )
            if guest:
                return guest
            author_vals = self._get_author_vals(gateway, author_id, update)
            if author_vals:
                return self.env["mail.guest"].create(author_vals)

        return False

    def _get_channel(self, gateway, token, update, force_create=False):
        tokens_to_try = [str(token)]
        if not str(token).startswith("+"):
            tokens_to_try.append("+" + str(token))
        if len(str(token)) == 12:
            tokens_to_try.append(str(token)[:4] + "9" + str(token)[4:])
        elif len(str(token)) == 13:
            tokens_to_try.append(str(token)[:4] + str(token)[5:])
        for candidate in tokens_to_try:
            chat_id = gateway._get_channel_id(candidate)
            if chat_id:
                return super()._get_channel(
                    gateway, candidate, update, force_create=force_create
                )
        author = self._get_author(gateway, update)
        if author and author._name == "res.partner":
            gc = self.env["res.partner.gateway.channel"].search(
                [
                    ("partner_id", "=", author.id),
                    ("gateway_id", "=", gateway.id),
                    ("gateway_token", "=", str(token)),
                ],
                limit=1,
            )
            if not gc:
                gc = self.env["res.partner.gateway.channel"].search(
                    [
                        ("partner_id", "=", author.id),
                        ("gateway_id", "=", gateway.id),
                    ],
                    limit=1,
                )
            if gc:
                for candidate in tokens_to_try:
                    existing_chat_id = gateway._get_channel_id(candidate)
                    if existing_chat_id:
                        return self.env["discuss.channel"].browse(existing_chat_id)
                existing_chat_id = gateway._get_channel_id(gc.gateway_token)
                if existing_chat_id:
                    return self.env["discuss.channel"].browse(existing_chat_id)
        return super()._get_channel(gateway, token, update, force_create=force_create)

    def _get_channel_vals(self, gateway, token, update):
        vals = super()._get_channel_vals(gateway, token, update)
        author = self._get_author(gateway, update)
        if author and author._name == "res.partner":
            vals["name"] = author.display_name
        return vals

    def _post_process_message(self, message, channel):
        return super()._post_process_message(message, channel)
