from odoo import api, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, *, message_type="notification", gateway_type=False, **kwargs):
        whatsapp_template_id = kwargs.pop("whatsapp_template_id", False)
        if whatsapp_template_id and self.gateway_id and self.gateway_id.gateway_type == "whatsapp":
            self = self.with_context(whatsapp_template_id=whatsapp_template_id)
        message = super().message_post(
            message_type=message_type,
            gateway_type=gateway_type,
            **kwargs,
        )
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
