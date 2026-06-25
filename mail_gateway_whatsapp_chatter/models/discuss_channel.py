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
        if self.gateway_id and self.gateway_id.gateway_type == "whatsapp" and message.message_type == "comment":
            self.env["mail.gateway.whatsapp"]._post_to_linked_threads(
                message.body, message.attachment_ids.ids, message.author_id, self
            )
        return message
