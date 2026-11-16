from odoo import fields, models
from odoo.exceptions import UserError

WHATSAPP_CALL_ACTION_TAG = "whatsapp_calling.initiate_business_call"


class ResPartner(models.Model):
    _inherit = "res.partner"

    def initiate_call_on_whatsapp(self):
        """Start a business initiated WhatsApp call.

        When the user has a single provider, the call is started by the tab
        that clicked the button (client action). This removes the dependency
        on the bus/websocket connection: without a connected bus the old
        implementation sent a notification that the browser never received,
        and the button appeared to do nothing.

        The multi-provider case still opens the provider selection wizard,
        handled by the original module.
        """
        if self.env.user.provider_ids and len(self.env.user.provider_ids) > 1:
            return super().initiate_call_on_whatsapp()

        if self.env.user.provider_id and self and self.mobile or self.phone:
            channel = self.env.user.provider_id.get_channel_whatsapp(self, self.env.user)
            channel_provider_line = fields.first(
                self.channel_provider_line_ids.filtered(
                    lambda line: line.provider_id == self.env.user.provider_id
                )
            )
            if channel and channel_provider_line.call_request_accepted:
                return {
                    "type": "ir.actions.client",
                    "tag": WHATSAPP_CALL_ACTION_TAG,
                    "params": {"payload": self._iomr_whatsapp_call_payload(channel)},
                }
            raise UserError(
                "This Customer haven't accepted the call request, "
                "Please send the call request template First"
            )
        return None

    def _iomr_whatsapp_call_payload(self, channel):
        """Payload consumed by the `whatsapp_calling.initiate_business_call`
        client action."""
        self.ensure_one()
        return {
            "type": "business_initiated_call_api_call",
            "call_rpc": True,
            "partner_id": self.id,
            "channel_id": channel.id if channel else False,
            "display_name": self.display_name,
            "avatar": self.image_128
            and f"/web/image/{self._name}/{self.id}/image_128"
            or False,
            "provider_id": self.env.user.provider_id.id,
        }

    def _compute_commission_related_html(self):
        """HTML com as comissões relacionadas ao parceiro.

        O campo ``commission_related_html`` é declarado como computado (sem
        ``store=True``) no módulo de comissões, portanto o ORM exige o método
        ``_compute_commission_related_html`` na leitura. Este método popula o
        cache com o HTML das comissões relacionadas ao parceiro (agentes/repasses).
        """
        for partner in self:
            commissions = self.env["commission.settlement"].sudo().search(
                [("agent_id", "=", partner.id)],
                order="date_from desc",
            )
            rows = []
            for settlement in commissions:
                rows.append(
                    "<tr>"
                    "<td>%s</td>"
                    "<td>%s</td>"
                    "<td>R$ %s</td>"
                    "</tr>"
                    % (
                        settlement.name or "Comissao",
                        settlement.date_from or "",
                        settlement.total or 0.0,
                    )
                )
            partner.commission_related_html = (
                "<div class='o_commission_related_html'>"
                "<table class='o_commission_related_html_table'>"
                "<tbody>%s</tbody>"
                "</table>"
                "</div>"
                % "".join(rows)
            )
