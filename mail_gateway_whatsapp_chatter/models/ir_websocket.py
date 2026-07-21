from odoo import models
from odoo.http import request

from odoo.addons.bus.websocket import wsrequest


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        req = request or wsrequest
        result = super()._build_bus_channel_list(channels)
        if req.session.uid:
            if req.env.user.has_group("mail_gateway.gateway_user"):
                user_channels = req.env["discuss.channel"].sudo().search(
                    [
                        ("channel_type", "=", "gateway"),
                        (
                            "channel_member_ids.partner_id",
                            "=",
                            req.env.user.partner_id.id,
                        ),
                    ]
                )
                for channel in user_channels:
                    result.append(channel)
                    result.append((channel, "members"))
        return result
