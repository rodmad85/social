from odoo import models


class MailNotification(models.Model):
    _inherit = "mail.notification"

    def _filtered_for_web_client(self):
        notifications = super()._filtered_for_web_client()
        # WhatsApp messages are synchronized between the gateway channel and
        # the related business document (chatter). Delivery failures must only
        # be exposed once, for the gateway channel: the chatter copy otherwise
        # adds a duplicate failure (and e-mail failures caused by the copy
        # posted on the document) to the messaging menu.
        return notifications.filtered(
            lambda notification: (
                not (
                    notification.mail_message_id.gateway_type == "whatsapp"
                    and notification.mail_message_id.model != "discuss.channel"
                    and notification.notification_status
                    in ("bounce", "exception", "canceled")
                )
            )
        )
