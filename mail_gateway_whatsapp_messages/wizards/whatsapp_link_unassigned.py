from odoo import api, fields, models


class WhatsappLinkUnassignedWizard(models.TransientModel):
    _name = "whatsapp.link.unassigned.wizard"
    _description = "Link Unassigned WhatsApp Conversations to CRM Leads"

    def _get_phone_candidates(self, token):
        token = str(token)
        candidates = [token]
        if not token.startswith("+"):
            candidates.append("+" + token)
        if len(token) == 12:
            candidates.append(token[:4] + "9" + token[4:])
        elif len(token) == 13:
            candidates.append(token[:4] + token[5:])
        return candidates

    def _find_matching_lead(self, channel):
        token = channel.gateway_channel_token
        if not token:
            return False
        phone_candidates = self._get_phone_candidates(token)
        for candidate in phone_candidates:
            partner = self.env["res.partner"].search([
                ("phone_sanitized", "=", candidate),
            ], limit=1)
            if partner:
                lead = self.env["crm.lead"].search([
                    ("partner_id", "=", partner.id),
                    ("type", "=", "opportunity"),
                ], limit=1)
                if lead:
                    return lead
        return False

    def action_link(self):
        self.ensure_one()
        unassigned = self.env["mail.whatsapp.conversation"].search([
            ("is_unassigned", "=", True),
        ])
        linked_count = 0
        skipped_count = 0
        for conversation in unassigned:
            channel = conversation.channel_id
            if not channel:
                skipped_count += 1
                continue
            lead = self._find_matching_lead(channel)
            if not lead:
                skipped_count += 1
                continue
            link = self.env["mail.whatsapp.chatter.link"].get_or_create(
                channel, lead
            )
            if lead.user_id and lead.user_id.partner_id:
                member = self.env["discuss.channel.member"].sudo().search([
                    ("channel_id", "=", channel.id),
                    ("partner_id", "=", lead.user_id.partner_id.id),
                ], limit=1)
                if not member:
                    self.env["discuss.channel.member"].sudo().create({
                        "channel_id": channel.id,
                        "partner_id": lead.user_id.partner_id.id,
                        "is_pinned": False,
                        "unpin_dt": False,
                    })
            linked_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Vinculação Concluída",
                "message": (
                    f"{linked_count} conversa(s) vinculada(s) a oportunidades. "
                    f"{skipped_count} conversa(s) ignorada(s) (sem oportunidade "
                    f"compatível)."
                ),
                "type": "success",
                "sticky": False,
            },
        }
