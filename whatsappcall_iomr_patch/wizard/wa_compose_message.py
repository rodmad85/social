from odoo import fields, models
from odoo.exceptions import UserError

from ..models.res_partner import WHATSAPP_CALL_ACTION_TAG


class WaComposeMessage(models.TransientModel):
    _inherit = "wa.compose.message"

    def call_on_whatsapp(self):
        """Provider selection wizard: start the call from the current tab
        instead of waiting for a bus notification."""
        for rec in self:
            if rec.provider_id and rec.partner_id and rec.partner_id.mobile or rec.partner_id.phone:
                channel = rec.provider_id.get_channel_whatsapp(rec.partner_id, self.env.user)
                channel_provider_line = fields.first(
                    rec.partner_id.channel_provider_line_ids.filtered(
                        lambda line: line.provider_id == rec.provider_id
                    )
                )
                if channel and channel_provider_line.call_request_accepted:
                    return {
                        "type": "ir.actions.client",
                        "tag": WHATSAPP_CALL_ACTION_TAG,
                        "params": {
                            "payload": rec._iomr_whatsapp_call_payload(channel),
                        },
                    }
                raise UserError(
                    "This Customer haven't accepted the call request, "
                    "Please send the call request template First"
                )
        return None

    def _iomr_whatsapp_call_payload(self, channel):
        self.ensure_one()
        return {
            "type": "business_initiated_call_api_call",
            "call_rpc": True,
            "partner_id": self.partner_id.id,
            "channel_id": channel.id if channel else False,
            "display_name": self.partner_id.display_name,
            "avatar": self.partner_id.image_128
            and f"/web/image/{self.partner_id._name}/{self.partner_id.id}/image_128"
            or False,
            "provider_id": self.provider_id.id,
        }
