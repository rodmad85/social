# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    whatsapp_gateway_id = fields.Many2one(
        "mail.gateway",
        string="WhatsApp Gateway",
        domain=[("gateway_type", "=", "whatsapp")],
        help="When a WhatsApp gateway is linked, incoming WhatsApp messages "
        "will be routed through this livechat channel.",
    )
