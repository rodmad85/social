from odoo import models


class MailGuestManage(models.TransientModel):
    _inherit = "mail.guest.manage"

    def _merge_partner(self, partner):
        self.env["res.partner.gateway.channel"]._get_or_create_for_gateway(
            partner,
            self.guest_id.gateway_id,
            self.guest_id.gateway_token,
        )
        for member in self.env["discuss.channel.member"].search(
            [("guest_id", "=", self.guest_id.id)]
        ):
            self.env["discuss.channel.member"].create(
                self._channel_member_vals(member, partner)
            )
            member.channel_id.name = partner.complete_name
            member.unlink()
        self.env["mail.message"].search(
            [("author_guest_id", "=", self.guest_id.id)]
        ).write(
            {
                "author_id": partner.id,
            }
        )