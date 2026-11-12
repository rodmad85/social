# Copyright 2024 Tecnativa - Carlos López
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import markupsafe

from odoo import api, fields, models


class MailComposeGatewayMessage(models.TransientModel):
    _inherit = "mail.compose.gateway.message"

    whatsapp_template_id = fields.Many2one(
        "mail.whatsapp.template",
        domain="""[
            ('state', '=', 'approved'),
            ('is_supported', '=', True),
            ('model', '=', model)
        ]""",
    )

    @api.onchange("whatsapp_template_id")
    def onchange_whatsapp_template_id(self):
        if self.whatsapp_template_id:
            self.body = markupsafe.Markup(
                self.whatsapp_template_id.with_context(
                    default_res_model=self.model,
                    default_res_id=self._get_compose_res_id(),
                ).render_body_message()
            )

    def _get_compose_res_id(self):
        """Return the first record id of the composer ``res_ids`` field."""
        self.ensure_one()
        res_ids = (self.res_ids or "").strip("[]").split(",")
        for res_id in res_ids:
            res_id = res_id.strip()
            if res_id:
                return int(res_id)
        return False

    def _action_send_mail(self, auto_commit=False):
        if self.whatsapp_template_id:
            self = self.with_context(
                whatsapp_template_id=self.whatsapp_template_id.id,
                default_res_model=self.model,
                default_res_id=self._get_compose_res_id(),
            )
        return super()._action_send_mail(auto_commit=auto_commit)
