from odoo import models
from odoo.exceptions import UserError


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _send(self, gateway, record, auto_commit=False, raise_exception=False, parse_mode=False):
        channel = record.gateway_channel_id
        if channel and channel.gateway_id and channel.gateway_id.gateway_type == "whatsapp":
            link = self.env["mail.whatsapp.chatter.link"].search(
                [("channel_id", "=", channel.id)], limit=1
            )
            if link:
                record_model = self.env[link.res_model].browse(link.res_id)
                if (
                    record_model.exists()
                    and "user_id" in record_model._fields
                    and record_model.user_id
                    and record_model.user_id != self.env.user
                ):
                    raise UserError(
                        self.env._(
                            "Only the assigned salesperson can send WhatsApp messages for this record."
                        )
                    )
        return super()._send(
            gateway,
            record,
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            parse_mode=parse_mode,
        )

    def _post_to_linked_threads(self, body, attachment_ids, author, chat):
        links = self.env["mail.whatsapp.chatter.link"].search(
            [("channel_id", "=", chat.id)]
        )
        for link in links:
            record = self.env[link.res_model].browse(link.res_id)
            if not record.exists():
                continue
            author_id = author.id if author and author._name == "res.partner" else False
            new_message = record.sudo().message_post(
                body=body,
                author_id=author_id,
                gateway_type="whatsapp",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                attachment_ids=attachment_ids,
            )
            follower_partners = (
                self.env["mail.followers"]
                .sudo()
                .search([
                    ("res_model", "=", link.res_model),
                    ("res_id", "=", link.res_id),
                ])
                .partner_id
            )
            for partner in follower_partners:
                partner.sudo()._bus_send_store(
                    new_message.sudo(),
                    notification_type="mail.record/insert",
                )

    def _post_process_message(self, message, channel):
        return super()._post_process_message(message, channel)
