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
                channel_member.sudo().create(
                    {
                        "partner_id": self.user_id.partner_id.id,
                        "channel_id": channel.id,
                        "is_pinned": False,
                        "unpin_dt": False,
                    }
                )
        return {"type": "ir.actions.act_window_close"}


class MailWhatsappConversation(models.Model):
    _name = "mail.whatsapp.conversation"
    _description = "WhatsApp Conversation grouped by contact"
    _rec_name = "display_name"
    _order = "last_message_date desc"
    _auto = False

    channel_id = fields.Many2one("discuss.channel", string="Canal", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Destinatário", readonly=True)
    author_partner_id = fields.Many2one("res.partner", string="Autor", readonly=True)
    author_user_id = fields.Many2one("res.users", string="Autor", readonly=True)
    gateway_id = fields.Many2one("mail.gateway", string="Gateway", readonly=True)
    last_message_date = fields.Datetime(string="Última mensagem", readonly=True)
    last_message_body = fields.Text(string="Última mensagem", readonly=True)
    message_count = fields.Integer(string="Quantidade", readonly=True)
    phone = fields.Char(string="Telefone", readonly=True)
    is_unassigned = fields.Boolean(string="Não atribuída", readonly=True)
    partner_user_id = fields.Many2one("res.users", string="Usuário", readonly=True)
    display_name = fields.Char(string="Destinatário", readonly=True)
    has_crm_lead = fields.Boolean(string="Vinculada a Oportunidade", readonly=True)

    def action_link_opportunity(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vincular Oportunidade",
            "res_model": "whatsapp.link.opportunity.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_channel_id": self.channel_id.id,
                "default_partner_id": self.partner_id.id if self.partner_id else False,
            },
        }

    def action_link_unassigned(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Vincular Não Atribuídas",
            "res_model": "whatsapp.link.unassigned.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_auto_assign_by_phone(self):
        self.env.cr.execute("""
            INSERT INTO discuss_channel_member (partner_id, channel_id, new_message_separator)
            SELECT ru.partner_id, dc.id, 0
            FROM discuss_channel dc
            JOIN res_partner rp ON (rp.phone_sanitized = '+' || dc.gateway_channel_token OR (rp.phone_sanitized = '+' || left(dc.gateway_channel_token, 4) || '9' || substring(dc.gateway_channel_token, 5) AND dc.gateway_channel_token ~ '^55[0-9]{2}'))
            JOIN res_users ru ON ru.id = rp.user_id AND ru.active = True
            WHERE dc.channel_type = 'gateway'
              AND dc.gateway_channel_token IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM discuss_channel_member dcm
                  JOIN res_users ru2 ON ru2.partner_id = dcm.partner_id
                  WHERE dcm.channel_id = dc.id AND ru2.active = True
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM discuss_channel_member dcm
                  WHERE dcm.channel_id = dc.id AND dcm.partner_id = ru.partner_id
              )
        """)
        return {"type": "ir.actions.act_window_close"}

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

    def action_assign_contact(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Assign Contact",
            "res_model": "whatsapp.assign.contact.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_channel_id": self.channel_id.id,
                "default_phone": self.phone,
            },
        }

    def action_open_channel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Mensagens",
            "res_model": "mail.message",
            "view_mode": "list",
            "views": [
                (
                    self.env.ref(
                        "mail_gateway_whatsapp_messages.mail_whatsapp_message_channel_tree_view"
                    ).id,
                    "list",
                )
            ],
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

    def action_claim(self):
        """Assume a conversa: adiciona o usuário atual como membro do canal.

        Sem isso, um usuário que não iniciou a conversa não a vê no Discuss
        (a regra de registro de discuss.channel limita o acesso aos canais
        dos quais ele é membro).
        """
        self.ensure_one()
        channel = self.channel_id
        if not channel:
            return False
        member = (
            self.env["discuss.channel.member"]
            .sudo()
            .search(
                [
                    ("channel_id", "=", channel.id),
                    ("partner_id", "=", self.env.user.partner_id.id),
                ],
                limit=1,
            )
        )
        if not member:
            self.env["discuss.channel.member"].sudo().create(
                {
                    "channel_id": channel.id,
                    "partner_id": self.env.user.partner_id.id,
                    "is_pinned": False,
                    "unpin_dt": False,
                }
            )
        return {
            "type": "ir.actions.client",
            "tag": "mail.action_discuss",
            "params": {"active_id": f"discuss.channel_{channel.id}"},
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self._init_indexes()
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW mail_whatsapp_conversation AS (
                SELECT
                    dc.id AS id,
                    dc.id AS channel_id,
                    COALESCE(contact_match.contact_partner_id, rp.id) AS partner_id,
                    rp.id AS author_partner_id,
                    ru.id AS author_user_id,
                    dc.gateway_id AS gateway_id,
                    lm.last_message_date AS last_message_date,
                    lm.last_message_body AS last_message_body,
                    COALESCE(mc.message_count, 0) AS message_count,
                    dc.gateway_channel_token AS phone,
                    COALESCE(rp_match.user_id, rp.user_id) AS partner_user_id,
                    CASE WHEN NOT EXISTS (
                        SELECT 1
                        FROM discuss_channel_member dcm
                        JOIN res_users ru_member ON ru_member.partner_id = dcm.partner_id
                        WHERE dcm.channel_id = dc.id
                          AND ru_member.active = TRUE
                    ) THEN TRUE ELSE FALSE END AS is_unassigned,
                    COALESCE(contact_match.contact_name, rp.name, dc.name, 'WhatsApp')
                        AS display_name,
                    CASE WHEN EXISTS (
                        SELECT 1
                        FROM mail_whatsapp_chatter_link crm_link
                        WHERE crm_link.channel_id = dc.id
                          AND crm_link.res_model = 'crm.lead'
                    ) THEN TRUE ELSE FALSE END AS has_crm_lead
                FROM discuss_channel dc
                JOIN mail_gateway gw ON gw.id = dc.gateway_id
                JOIN LATERAL (
                    SELECT ms.date AS last_message_date,
                           ms.body AS last_message_body,
                           ms.author_id AS author_id
                    FROM mail_message ms
                    WHERE ms.model = 'discuss.channel'
                      AND ms.res_id = dc.id
                      AND ms.gateway_type = 'whatsapp'
                    ORDER BY ms.date DESC
                    LIMIT 1
                ) lm ON TRUE
                LEFT JOIN res_partner rp ON rp.id = lm.author_id
                LEFT JOIN res_users ru ON ru.partner_id = rp.id
                LEFT JOIN LATERAL (
                    SELECT COUNT(ms.id) AS message_count
                    FROM mail_message ms
                    WHERE ms.model = 'discuss.channel'
                      AND ms.res_id = dc.id
                      AND ms.gateway_type = 'whatsapp'
                ) mc ON TRUE
                LEFT JOIN LATERAL (
                    SELECT rp2.user_id AS user_id
                    FROM res_partner rp2
                    WHERE dc.gateway_channel_token IS NOT NULL
                      AND (
                          rp2.phone_sanitized = '+' || dc.gateway_channel_token
                          OR (
                              rp2.phone_sanitized = '+'
                              || left(dc.gateway_channel_token, 4)
                              || '9'
                              || substring(dc.gateway_channel_token, 5)
                              AND dc.gateway_channel_token ~ '^55[0-9]{2}'
                          )
                      )
                      AND rp2.user_id IS NOT NULL
                    LIMIT 1
                ) rp_match ON TRUE
                LEFT JOIN LATERAL (
                    SELECT rp3.id AS contact_partner_id, rp3.name AS contact_name
                    FROM res_partner rp3
                    WHERE dc.gateway_channel_token IS NOT NULL
                      AND (
                          rp3.phone_sanitized = '+' || dc.gateway_channel_token
                          OR (
                              rp3.phone_sanitized = '+'
                              || left(dc.gateway_channel_token, 4)
                              || '9'
                              || substring(dc.gateway_channel_token, 5)
                              AND dc.gateway_channel_token ~ '^55[0-9]{2}'
                          )
                      )
                    LIMIT 1
                ) contact_match ON TRUE
                WHERE gw.gateway_type = 'whatsapp'
                  AND dc.channel_type = 'gateway'
            )
        """)
        self.action_auto_assign_by_phone()

    def _init_indexes(self):
        """Cria os índices que sustentam a view de conversas.

        A view é executada a cada abertura do menu Conversas. Sem estes
        índices o PostgreSQL varre mail_message e res_partner inteiros.
        """
        self._ensure_index(
            "mail_message",
            "mail_message_wa_channel_date_idx",
            "(model, gateway_type, res_id, date DESC)",
        )
        self._ensure_index(
            "discuss_channel",
            "discuss_channel_wa_token_idx",
            "(gateway_channel_token)",
            "gateway_channel_token IS NOT NULL",
        )
        self._ensure_index(
            "res_partner",
            "res_partner_phone_sanitized_wa_idx",
            "(phone_sanitized)",
            "phone_sanitized IS NOT NULL",
        )
        self._ensure_index(
            "mail_whatsapp_chatter_link",
            "mail_whatsapp_chatter_link_channel_idx",
            "(channel_id, res_model)",
        )

    @api.model
    def _ensure_index(self, table, index_name, columns, where_clause=""):
        cr = self.env.cr
        cr.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        if not cr.fetchone():
            return
        cr.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = %s",
            (table,),
        )
        for (indexdef,) in cr.fetchall():
            if columns in indexdef:
                return
        statement = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} {columns}"
        if where_clause:
            statement += f" WHERE {where_clause}"
        cr.execute(statement)
