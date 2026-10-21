# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MailWhatsappConversation(models.Model):
    _inherit = "mail.whatsapp.conversation"

    def action_auto_assign_by_phone(self):
        """Quando 'Mensagens não atribuídas' está configurado para
        'Atribuir diretamente a um usuário', atribui os canais não atribuídos
        diretamente ao usuário definido em Definições > WhatsApp Central, em
        vez de tentar associar pelo telefone."""
        ICPSudo = self.env["ir.config_parameter"].sudo()
        action = ICPSudo.get_param(
            "whatsapp_central_settings.wa_unassigned_action"
        ) or "list"
        user_id = ICPSudo.get_param(
            "whatsapp_central_settings.wa_unassigned_user_id"
        )
        user_id = int(user_id) if user_id else False

        if action == "assign" and user_id:
            # Atribui diretamente canais gateway (WhatsApp) sem membro ativo ao
            # usuário configurado.
            self.env.cr.execute(
                """
                INSERT INTO discuss_channel_member (
                    partner_id, channel_id, new_message_separator, is_pinned
                )
                SELECT ru.partner_id, dc.id, 0, FALSE
                FROM discuss_channel dc
                JOIN res_users ru ON ru.id = %s
                WHERE dc.channel_type = 'gateway'
                  AND dc.gateway_channel_token IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM discuss_channel_member dcm
                      WHERE dcm.channel_id = dc.id
                        AND dcm.partner_id = ru.partner_id
                  )
                """,
                (user_id,),
            )
            return {"type": "ir.actions.act_window_close"}

        return super().action_auto_assign_by_phone()
