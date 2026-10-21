# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, _
from odoo.exceptions import AccessError

PARAM_PREFIX = "whatsapp_central_settings."


class MailWhatsAppTemplate(models.Model):
    _inherit = "mail.whatsapp.template"

    def _check_edit_permission(self):
        """Impede criar/editar/excluir templates de WhatsApp para usuários que
        não estejam na lista 'Editar templates de mensagem — quem pode editar'
        configurada em Definições > WhatsApp Central.

        Usuários do grupo base.group_system (administradores) são sempre
        liberados."""
        ICPSudo = self.env["ir.config_parameter"].sudo()
        raw = ICPSudo.get_param(PARAM_PREFIX + "wa_template_edit_user_ids") or ""
        allowed_ids = [int(x) for x in raw.split(",") if x.strip()]

        if self.env.user.has_group("base.group_system"):
            return

        if not allowed_ids:
            # Nenhum usuário configurado: bloqueia edição para todos (exceto admin)
            raise AccessError(
                _("Nenhum usuário está autorizado a editar templates de mensagem "
                  "do WhatsApp. Configure em Definições > WhatsApp Central.")
            )

        if self.env.user.id not in allowed_ids:
            raise AccessError(
                _("Você não tem permissão para editar templates de mensagem do "
                  "WhatsApp. Procure o administrador para ser adicionado à lista "
                  "de usuários autorizados em Definições > WhatsApp Central.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_edit_permission()
        return super().create(vals_list)

    def write(self, vals):
        self._check_edit_permission()
        return super().write(vals)

    def unlink(self):
        self._check_edit_permission()
        return super().unlink()
