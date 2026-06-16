from odoo import api, fields, models


class MailChannel(models.Model):
    _inherit = "discuss.channel"

    is_unassigned = fields.Boolean(
        string="Unassigned",
        compute="_compute_is_unassigned",
        store=True,
    )

    transfer_target_user_id = fields.Many2one(
        "res.users",
        string="Transferir para",
        help="Usuário para quem a conversa será transferida",
    )
    transfer_state = fields.Selection(
        [
            ("pending", "Pendente"),
            ("approved", "Aprovada"),
            ("rejected", "Rejeitada"),
        ],
        string="Estado da Transferência",
    )
    transfer_requested_by = fields.Many2one(
        "res.users",
        string="Solicitado por",
        default=lambda self: self.env.user,
    )
    transfer_requested_date = fields.Datetime(
        string="Data da Solicitação",
        default=fields.Datetime.now,
    )
    transfer_message = fields.Text(string="Motivo da Transferência")

    @api.depends("channel_type", "channel_member_ids")
    def _compute_is_unassigned(self):
        for channel in self:
            if channel.channel_type != "gateway":
                channel.is_unassigned = False
                continue
            assigned = any(
                member.partner_id and member.partner_id.user_ids
                for member in channel.channel_member_ids
            )
            channel.is_unassigned = not assigned

    def action_claim(self):
        self.ensure_one()
        self.env["discuss.channel.member"].sudo().create(
            {
                "partner_id": self.env.user.partner_id.id,
                "channel_id": self.id,
                "is_pinned": False,
                "unpin_dt": False,
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "mail.action_discuss",
            "params": {"active_id": f"{self._name}_{self.id}"},
        }

    def action_request_transfer(self):
        self.ensure_one()
        context = dict(self.env.context)
        return {
            "type": "ir.actions.act_window",
            "res_model": "discuss.channel.transfer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_channel_id": self.id,
                "default_channel_name": self.name,
            },
        }

    def action_approve_transfer(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            return
        target_user = self.transfer_target_user_id
        if target_user:
            self.env["discuss.channel.member"].sudo().create(
                {
                    "partner_id": target_user.partner_id.id,
                    "channel_id": self.id,
                    "is_pinned": False,
                    "unpin_dt": False,
                }
            )
        self.transfer_state = "approved"

    def action_reject_transfer(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            return
        self.transfer_state = "rejected"

    def _auto_link_opportunity(self):
        self.ensure_one()
        if self.channel_type != "gateway":
            return
        if not self.env.registry.get("crm.lead") or not self.env.registry.get("mail.whatsapp.chatter.link"):
            return
        Contact = self.env["res.partner"]
        partner = Contact.search(
            [("gateway_channel_ids.channel_id", "=", self.id)], limit=1
        )
        if not partner:
            return
        phone = partner.mobile or partner.phone
        if not phone:
            return
        clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
        leads = self.env["crm.lead"].search(
            [
                "|",
                ("phone", "!=", False),
                ("mobile", "!=", False),
            ]
        )
        for lead in leads:
            lead_phone = (lead.phone or lead.mobile or "").replace(
                " ", ""
            ).replace("-", "").replace("+", "")
            if clean_phone in lead_phone or lead_phone in clean_phone:
                Link = self.env["mail.whatsapp.chatter.link"]
                Link.get_or_create(self, lead)

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, *, message_type="notification", gateway_type=False, **kwargs):
        if (
            self.gateway_id
            and self.channel_type == "gateway"
            and message_type != "notification"
        ):
            current_partner = self.env.user.partner_id
            if not any(
                member.partner_id == current_partner
                for member in self.channel_member_ids
            ):
                self.env["discuss.channel.member"].sudo().create(
                    {
                        "partner_id": current_partner.id,
                        "channel_id": self.id,
                        "is_pinned": False,
                        "unpin_dt": False,
                    }
                )
            self._auto_link_opportunity()
        return super().message_post(
            message_type=message_type, gateway_type=gateway_type, **kwargs
        )
