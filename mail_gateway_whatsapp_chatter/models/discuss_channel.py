from odoo import api, fields, models
from odoo.exceptions import UserError


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _check_template_send_allowed(self, template_id):
        self.ensure_one()
        last_send = self.env["mail.whatsapp.template.send"].search([
            ("template_id", "=", template_id),
            ("channel_id", "=", self.id),
        ], limit=1)
        if not last_send:
            return
        last_send_dt = fields.Datetime.from_string(last_send.send_date)
        now_dt = fields.Datetime.from_string(fields.Datetime.now())
        diff = (now_dt - last_send_dt).total_seconds()
        if diff < 86400:
            has_response = self.message_ids.filtered(
                lambda m: (
                    m.date > last_send.send_date
                    and m.gateway_type == "whatsapp"
                    and m.author_id
                    and m.author_id != self.env.user.partner_id
                )
            )
            if not has_response:
                raise UserError(
                    self.env._(
                        "Não é permitido enviar a mesma mensagem template "
                        "dentro de 24h sem que o contato tenha respondido."
                    )
                )

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, *, message_type="notification", gateway_type=False, **kwargs):
        whatsapp_template_id = kwargs.pop("whatsapp_template_id", False)
        if not whatsapp_template_id:
            whatsapp_template_id = self.env.context.get("whatsapp_template_id", False)
        if whatsapp_template_id and self.gateway_id and self.gateway_id.gateway_type == "whatsapp":
            self = self.with_context(whatsapp_template_id=whatsapp_template_id)
        if whatsapp_template_id:
            self._check_template_send_allowed(whatsapp_template_id)
        message = super().message_post(
            message_type=message_type,
            gateway_type=gateway_type,
            **kwargs,
        )
        if whatsapp_template_id and message and message.message_type == "comment" and not message.gateway_message_id:
            self.env["mail.whatsapp.template.send"].create({
                "template_id": whatsapp_template_id,
                "channel_id": self.id,
                "message_id": message.id,
            })
        if self.gateway_id and self.gateway_id.gateway_type == "whatsapp" and message.message_type == "comment" and not message.gateway_message_id :
            self.env["mail.gateway.whatsapp"]._post_to_linked_threads(
                message.body, message.attachment_ids.ids, message.author_id, self
            )
        return message

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        rdata = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)
        if self.gateway_id and self.gateway_id.gateway_type == "whatsapp" and message.message_type == "comment":
            for member in self.channel_member_ids:
                partner = member.partner_id
                if partner and partner.user_ids:
                    for user in partner.user_ids.filtered(lambda u: u.active):
                        user._bus_send_store(
                            message.with_user(user).with_context(allowed_company_ids=[]),
                            notification_type="mail.record/insert",
                        )
        return rdata
