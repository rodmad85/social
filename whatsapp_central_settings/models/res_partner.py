# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.depends_context("uid")
    def _compute_user_can_make_whatsapp_call(self):
        icp = self.env["ir.config_parameter"].sudo()
        param = icp.get_param("whatsapp_central_settings.wa_call_make_user_ids") or ""
        allowed_ids = {int(x) for x in param.split(",") if x.strip()}
        current_uid = self.env.user.id
        for partner in self:
            partner.user_can_make_whatsapp_call = current_uid in allowed_ids

    user_can_make_whatsapp_call = fields.Boolean(
        string="User can make WhatsApp calls",
        compute="_compute_user_can_make_whatsapp_call",
        store=False,
        help="Indicates if the current user is allowed to make WhatsApp calls "
        "according to WhatsApp Central Settings.",
    )
