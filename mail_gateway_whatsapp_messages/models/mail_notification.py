from odoo import models

from odoo.addons.mail.tools.discuss import Store


class MailNotification(models.Model):
    _inherit = "mail.notification"

    def _to_store(self, store: Store, /):
        # sudo: 'discuss.channel' - the inherited implementation (mail_gateway)
        # serializes ``channel_name``, reading the gateway channel of the
        # notification. Gateway channels are restricted to their members by the
        # record rule "discuss.channel: access gateway (restricted)", so users
        # allowed to read the thread but not a member of that channel were
        # getting an AccessError, which aborted the whole request: the chatter
        # then failed with "An error occurred while fetching messages.
        # RPC_ERROR: Odoo Server Error" (e.g. crm.lead chatter with WhatsApp
        # messages). Serializing notifications is display only, hence sudo.
        return super(MailNotification, self.sudo())._to_store(store)
