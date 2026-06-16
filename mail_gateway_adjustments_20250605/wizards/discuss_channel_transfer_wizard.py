from odoo import api, fields, models


class DiscussChannelTransferWizard(models.TransientModel):
    _name = "discuss.channel.transfer.wizard"
    _description = "Wizard to request channel transfer"

    channel_id = fields.Many2one("discuss.channel", required=True)
    channel_name = fields.Char(related="channel_id.name", readonly=True)
    target_user_id = fields.Many2one(
        "res.users",
        string="Transferir para",
        required=True,
    )
    message = fields.Text(string="Motivo")

    @api.onchange("target_user_id")
    def _onchange_target_user_id(self):
        if self.target_user_id and not self.target_user_id.has_group("mail_gateway.gateway_user"):
            return {
                "warning": {
                    "title": "Usuário inválido",
                    "message": "O usuário selecionado não faz parte do grupo Gateway.",
                },
                "value": {"target_user_id": False},
            }

    def action_submit(self):
        self.ensure_one()
        channel = self.channel_id
        channel.write({
            "transfer_target_user_id": self.target_user_id.id,
            "transfer_state": "pending",
            "transfer_requested_by": self.env.user.id,
            "transfer_requested_date": fields.Datetime.now(),
            "transfer_message": self.message,
        })
        admins = self.env.ref("base.group_system").users
        notification_body = (
            f"Solicitação de transferência da conversa '{channel.name}' "
            f"para {self.target_user_id.name} por {self.env.user.name}."
        )
        for admin in admins:
            channel.message_post(
                body=notification_body,
                message_type="notification",
                partner_ids=[admin.partner_id.id],
            )
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": "Solicitação enviada",
            "message": f"Solicitação de transferência para {self.target_user_id.name} enviada para aprovação.",
            "sticky": False,
            "type": "success",
        }}
