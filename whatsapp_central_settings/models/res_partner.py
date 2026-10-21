# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def whatsapp_call_from_chatter(self, model, res_id):
        """Inicia uma chamada de WhatsApp a partir do chatter.

        Recebe o model e o res_id do registro exibido no chatter, resolve o
        parceiro e dispara a chamada (ou abre o wizard de chamada quando houver
        vários provedores configurados).
        """
        record = self.env[model].browse(res_id)
        if model == "res.partner":
            partner = record
        elif hasattr(record, "partner_id") and record.partner_id:
            partner = record.partner_id
        else:
            partner = False

        if not partner:
            raise UserError(_("No partner found to start the WhatsApp call."))

        user = self.env.user
        if user.provider_ids and len(user.provider_ids) > 1:
            # Vários provedores: abre o wizard de composição para escolher.
            return {
                "type": "ir.actions.act_window",
                "name": _("Call on WhatsApp"),
                "res_model": "wa.compose.message",
                "target": "new",
                "view_mode": "form",
                "context": {
                    "active_model": model,
                    "active_id": res_id,
                    "whatsapp_call": True,
                    "field_name": "phone",
                },
            }

        if user.provider_id and (partner.mobile or partner.phone):
            channel = user.provider_id.get_channel_whatsapp(partner, user)
            channel_provider_line = fields.first(
                partner.channel_provider_line_ids.filtered(
                    lambda s: s.provider_id == user.provider_id
                )
            )
            if channel and channel_provider_line.call_request_accepted:
                bus_payload = {
                    "type": "business_initiated_call_api_call",
                    "call_rpc": True,
                    "partner_id": partner.id,
                    "channel_id": channel.id if channel else False,
                    "display_name": partner.display_name,
                    "avatar": partner.image_128
                    and f"/web/image/{partner._name}/{partner.id}/image_128"
                    or False,
                    "provider_id": user.provider_id.id,
                }
                self.env["bus.bus"].sudo()._sendone(
                    user.partner_id,
                    "whatsapp_call_service",
                    bus_payload,
                )
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("WhatsApp Call"),
                        "message": _("Call request sent."),
                        "type": "success",
                        "sticky": False,
                    },
                }
            raise UserError(
                _(
                    "This Customer have not accepted the call request, "
                    "Please send the call request template First"
                )
            )

        raise UserError(
            _("No WhatsApp provider or phone number configured for this partner.")
        )

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
