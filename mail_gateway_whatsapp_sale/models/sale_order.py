# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _whatsapp_phone_field_name(self):
        """Return the customer phone field used to resolve the channel."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(
                self.env._(
                    "You must set a customer before sending the order by WhatsApp."
                )
            )
        return "mobile" if self.partner_id.mobile else "phone"

    def _whatsapp_get_channel(self, field_name, gateway):
        """Resolve the WhatsApp channel from the customer phone number.

        The channel is a technical record, so it is created with ``sudo()``
        to allow any user with access to the document to send the message.
        """
        self.ensure_one()
        return self.partner_id.sudo()._whatsapp_get_channel(
            self._whatsapp_phone_field_name(), gateway
        )

    def _whatsapp_get_attachments(self):
        """Return the quotation PDF to be sent with the WhatsApp message.

        The PDF is generated once per order and reused on subsequent sends.
        """
        self.ensure_one()
        report = self.env.ref("sale.action_report_saleorder")
        doc_name = self.name if self.name and self.name != "/" else "Quotation"
        filename = f"{doc_name}.pdf"
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("name", "=", filename),
            ],
            limit=1,
        )
        if not attachment:
            pdf_content = self.env["ir.actions.report"]._render_qweb_pdf(
                report, self.ids
            )[0]
            attachment = self.env["ir.attachment"].create(
                {
                    "name": filename,
                    "raw": pdf_content,
                    "mimetype": "application/pdf",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        return attachment

    def action_send_whatsapp(self):
        """Open the WhatsApp composer to send the order to the customer."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "mail_gateway_whatsapp.whatsapp_composer_act_window"
        )
        action["context"] = {
            "default_res_model": self._name,
            "default_res_id": self.id,
            "default_number_field_name": "partner_id",
        }
        return action
