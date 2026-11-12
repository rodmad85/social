from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    whatsapp_author_name = fields.Char(
        compute="_compute_whatsapp_author_name",
        string="Autor",
    )
    whatsapp_author_mobile = fields.Char(
        compute="_compute_whatsapp_author_mobile",
        string="WhatsApp Mobile",
    )

    @api.depends("author_id", "author_guest_id", "gateway_type")
    def _compute_whatsapp_author_name(self):
        for msg in self:
            if msg.gateway_type != "whatsapp":
                msg.whatsapp_author_name = False
            elif msg.author_id:
                msg.whatsapp_author_name = msg.author_id.name
            elif msg.author_guest_id:
                msg.whatsapp_author_name = msg.author_guest_id.name
            else:
                msg.whatsapp_author_name = "Desconhecido"

    @api.depends("author_id", "author_guest_id", "gateway_type", "model", "res_id")
    def _compute_whatsapp_author_mobile(self):
        """Retorna o mobile (WhatsApp) correspondente ao autor da mensagem.

        Mensagens recebidas de contatos do WhatsApp costumam ter um convidado
        (``mail.guest``) como autor, ou um parceiro sem ``mobile``/``phone``
        preenchido. Nesses casos o número do contato está no token do canal de
        gateway, que é usado como fallback para que o número apareça também
        nas conversas já existentes.
        """
        for msg in self:
            mobile = False
            if msg.gateway_type == "whatsapp":
                if msg.author_id:
                    mobile = msg.author_id.mobile or msg.author_id.phone or False
                author_is_contact = not msg.author_id or not msg.author_id.user_id
                if (
                    not mobile
                    and author_is_contact
                    and msg.model == "discuss.channel"
                    and msg.res_id
                ):
                    channel = self.env["discuss.channel"].browse(msg.res_id)
                    if channel.gateway_id.gateway_type == "whatsapp":
                        mobile = channel.gateway_channel_token or False
            msg.whatsapp_author_mobile = mobile or ""

    @api.depends("gateway_type", "author_id", "author_guest_id")
    def _compute_is_whatsapp_incoming(self):
        current_partner = self.env.user.partner_id
        for msg in self:
            if msg.gateway_type == "whatsapp":
                if msg.author_id and msg.author_id != current_partner or msg.author_guest_id and not msg.author_id:
                    msg.is_whatsapp_incoming = True
                else:
                    msg.is_whatsapp_incoming = False
            else:
                msg.is_whatsapp_incoming = False
