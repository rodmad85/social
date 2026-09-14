# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests import RecordCapturer
from odoo.tests.common import tagged

from odoo.addons.mail_gateway.tests.common import MailGatewayTestCase


@tagged("-at_install", "post_install")
class TestSaleOrderWhatsapp(MailGatewayTestCase):
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
                "name": "Order Template",
                "category": "utility",
                "language": "es",
                "body": "Demo template",
                "state": "approved",
                "is_supported": True,
                "gateway_id": cls.gateway.id,
                "model_id": cls.env["ir.model"]._get("sale.order").id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Partner", "mobile": "+34 600 000 001"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "type": "consu"}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "name": "Test line",
                            "product_id": cls.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )

    def test_action_send_whatsapp(self):
        action = self.order.action_send_whatsapp()
        self.assertEqual(action["res_model"], "whatsapp.composer")
        self.assertEqual(action["context"]["default_res_model"], "sale.order")
        self.assertEqual(action["context"]["default_res_id"], self.order.id)
        self.assertEqual(action["context"]["default_number_field_name"], "partner_id")

    def test_whatsapp_get_channel_partner_number(self):
        channel = self.order._whatsapp_get_channel("partner_id", self.gateway)
        self.assertTrue(channel)
        self.assertEqual(channel.gateway_channel_token, "34600000001")
        self.assertEqual(channel.gateway_id, self.gateway)

    def test_whatsapp_get_attachments(self):
        attachment = self.order._whatsapp_get_attachments()
        self.assertTrue(attachment)
        self.assertEqual(attachment.mimetype, "application/pdf")
        self.assertEqual(attachment.res_model, "sale.order")
        self.assertEqual(attachment.res_id, self.order.id)

    def test_send_order_by_whatsapp(self):
        composer = self.env["whatsapp.composer"].create(
            {
                "res_model": "sale.order",
                "res_id": self.order.id,
                "number_field_name": "partner_id",
                "gateway_id": self.gateway.id,
                "body": "Test body",
            }
        )
        channel = self.order._whatsapp_get_channel("partner_id", self.gateway)
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
