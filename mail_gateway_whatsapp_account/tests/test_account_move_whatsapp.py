# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock, patch

from odoo.tests import RecordCapturer
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("-at_install", "post_install")
class TestAccountMoveWhatsapp(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gateway = cls.env["mail.gateway"].create(
            {
                "name": "WhatsApp Gateway",
                "gateway_type": "whatsapp",
                "token": "gateway-token",
                "whatsapp_security_key": "security-key",
                "webhook_secret": "MY-SECRET",
                "member_ids": [(4, cls.env.user.id)],
            }
        )
        cls.ws_template = cls.env["mail.whatsapp.template"].create(
            {
                "name": "Invoice Template",
                "category": "utility",
                "language": "es",
                "body": "Demo template",
                "state": "approved",
                "is_supported": True,
                "gateway_id": cls.gateway.id,
                "model_id": cls.env["ir.model"]._get("account.move").id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Customer", "mobile": "+34 600 000 002"}
        )
        cls.invoice = cls._create_invoice(
            move_type="out_invoice",
            partner_id=cls.partner,
            invoice_date="2026-01-01",
        )

    def test_action_send_whatsapp(self):
        action = self.invoice.action_send_whatsapp()
        self.assertEqual(action["res_model"], "whatsapp.composer")
        self.assertEqual(action["context"]["default_res_model"], "account.move")
        self.assertEqual(action["context"]["default_res_id"], self.invoice.id)
        self.assertEqual(action["context"]["default_number_field_name"], "partner_id")

    def test_whatsapp_get_channel_partner_number(self):
        channel = self.invoice._whatsapp_get_channel("partner_id", self.gateway)
        self.assertTrue(channel)
        self.assertEqual(channel.gateway_channel_token, "34600000002")
        self.assertEqual(channel.gateway_id, self.gateway)

    def test_whatsapp_get_attachments(self):
        attachment = self.invoice._whatsapp_get_attachments()
        self.assertTrue(attachment)
        self.assertEqual(attachment.mimetype, "application/pdf")
        self.assertEqual(attachment.res_model, "account.move")
        self.assertEqual(attachment.res_id, self.invoice.id)

    def test_send_invoice_by_whatsapp(self):
        composer = self.env["whatsapp.composer"].create(
            {
                "res_model": "account.move",
                "res_id": self.invoice.id,
                "number_field_name": "partner_id",
                "gateway_id": self.gateway.id,
                "body": "Test body",
            }
        )
        channel = self.invoice._whatsapp_get_channel("partner_id", self.gateway)
        message_domain = [
            ("gateway_type", "=", "whatsapp"),
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
        ]
        with (
            RecordCapturer(self.env["mail.message"], message_domain) as capture,
            patch("requests.post", return_value=MagicMock()),
        ):
            composer.action_send_whatsapp()
        self.assertEqual(len(capture.records), 1)
        self.assertTrue(capture.records.attachment_ids)
        self.assertEqual(capture.records.notification_ids.notification_status, "sent")
