from odoo import api, fields, models, tools


class WhatsappAssignConversationWizard(models.TransientModel):
    _name = "whatsapp.assign.conversation.wizard"
    _description = "Assign WhatsApp Conversations"

    user_id = fields.Many2one("res.users", string="Usuário", required=True)
    conversation_ids = fields.Many2many(
        "mail.whatsapp.conversation", "whatsapp_assign_conv_rel", string="Conversas"
    )

    def action_assign(self):
        self.ensure_one()
        for conversation in self.conversation_ids:
            channel = conversation.channel_id
            channel_member = self.env["discuss.channel.member"]
            if not any(
                m.partner_id == self.user_id.partner_id
                for m in channel.channel_member_ids
            ):
                channel_member.sudo().create({
                    "partner_id": self.user_id.partner_id.id,
                    "channel_id": channel.id,
                    "is_pinned": False,
                    "unpin_dt": False,
                })
        return {"type": "ir.actions.act_window_close"}


class MailWhatsappConversation(models.Model):
    _name = "mail.whatsapp.conversation"
    _description = "WhatsApp Conversation grouped by contact"
    _rec_name = "display_name"
    _order = "last_message_date desc"
    _auto = False

    channel_id = fields.Many2one("discuss.channel", string="Canal", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contato", readonly=True)
    gateway_id = fields.Many2one("mail.gateway", string="Gateway", readonly=True)
    last_message_date = fields.Datetime(string="Última mensagem", readonly=True)
    last_message_body = fields.Text(string="Última mensagem", readonly=True)
    message_count = fields.Integer(string="Quantidade", readonly=True)
    is_unassigned = fields.Boolean(string="Não atribuída", readonly=True)
    display_name = fields.Char(string="Contato", readonly=True)

    def action_assign_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Atribuir Conversa",
            "res_model": "whatsapp.assign.conversation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_conversation_ids": [(6, 0, self.ids)],
            },
        }

    def action_open_channel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Mensagens",
            "res_model": "mail.message",
            "view_mode": "kanban",
            "views": [(self.env.ref("mail_gateway_whatsapp_messages.mail_whatsapp_message_kanban_view").id, "kanban")],
            "domain": [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.channel_id.id),
                ("gateway_type", "=", "whatsapp"),
            ],
            "context": dict(
                self.env.context,
                search_default_group_contact=False,
            ),
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW mail_whatsapp_conversation AS (
                WITH latest_messages AS (
                    SELECT DISTINCT ON (dc.id)
                        dc.id AS channel_id,
                        dc.gateway_id,
                        ms.date AS last_message_date,
                        ms.body AS last_message_body,
                        ms.author_id
                    FROM mail_message ms
                    JOIN discuss_channel dc ON dc.id = ms.res_id
                    WHERE ms.gateway_type = 'whatsapp'
                      AND ms.model = 'discuss.channel'
                    ORDER BY dc.id, ms.date DESC
                ),
                message_counts AS (
                    SELECT
                        ms.res_id AS channel_id,
                        COUNT(ms.id) AS msg_count
                    FROM mail_message ms
                    WHERE ms.gateway_type = 'whatsapp'
                      AND ms.model = 'discuss.channel'
                    GROUP BY ms.res_id
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY lm.last_message_date DESC NULLS LAST) AS id,
                    lm.channel_id,
                    rp.id AS partner_id,
                    lm.gateway_id,
                    lm.last_message_date,
                    lm.last_message_body,
                    COALESCE(mc.msg_count, 0) AS message_count,
                    CASE WHEN NOT EXISTS (
                        SELECT 1
                        FROM discuss_channel_member dcm
                        JOIN res_users ru ON ru.partner_id = dcm.partner_id
                        WHERE dcm.channel_id = lm.channel_id
                          AND ru.active = True
                        LIMIT 1
                    ) AND (
                        rp.user_id IS NULL
                        OR NOT EXISTS (
                            SELECT 1
                            FROM res_users ru
                            WHERE ru.id = rp.user_id
                              AND ru.active = True
                            LIMIT 1
                        )
                    ) THEN TRUE ELSE FALSE END AS is_unassigned,
                    COALESCE(rp.name, dc.name, 'WhatsApp') AS display_name
                FROM latest_messages lm
                JOIN discuss_channel dc ON dc.id = lm.channel_id
                LEFT JOIN res_partner rp ON rp.id = lm.author_id
                LEFT JOIN message_counts mc ON mc.channel_id = lm.channel_id
            )
        """)
