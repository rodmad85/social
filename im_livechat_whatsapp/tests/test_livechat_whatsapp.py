# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestLivechatWhatsapp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # Create operator user
        cls.operator_user = cls.env["res.users"].create(
            {
                "name": "Operator",
                "login": "operator_livechat_wa",
                "password": "operator_livechat_wa",
                "groups_id": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("im_livechat.im_livechat_group_user").id),
                ],
            }
        )
        # Create a WhatsApp gateway
        cls.gateway = cls.env["mail.gateway"].create(
            {
                "name": "WA Gateway",
                "gateway_type": "whatsapp",
                "token": "test_token",
                "whatsapp_security_key": "test_key",
                "webhook_secret": "MY-SECRET",
                "member_ids": [(4, cls.operator_user.id)],
            }
        )
        # Create a livechat channel linked to the gateway
        cls.livechat_channel = cls.env["im_livechat.channel"].create(
            {
                "name": "WhatsApp Support",
                "user_ids": [(4, cls.operator_user.id)],
                "whatsapp_gateway_id": cls.gateway.id,
            }
        )
        # WhatsApp inbound message payload
        cls.wa_message = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "1234",
                                    "phone_number_id": "34600000000",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Test Visitor"},
                                        "wa_id": "34600000000",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "34600000000",
                                        "id": "wamid.TEST123",
                                        "timestamp": "1700000000",
                                        "text": {"body": "Hello from WhatsApp"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

    def _setup_webhook(self):
        """Helper to set up and integrate the webhook."""
        self.gateway.webhook_key = "test_hook"
        self.gateway.set_webhook()
        self.url_open(
            f"/gateway/{self.gateway.gateway_type}/{self.gateway.webhook_key}"
            f"/update?hub.verify_token={self.gateway.whatsapp_security_key}"
            f"&hub.challenge=22",
        )
        self.assertEqual(self.gateway.integrated_webhook_state, "integrated")

    def _send_webhook_message(self, message):
        """Send a webhook message with proper HMAC signature."""
        data = json.dumps(message)
        hex_dig = hmac.new(
            self.gateway.webhook_secret.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.url_open(
            f"/gateway/{self.gateway.gateway_type}"
            f"/{self.gateway.webhook_key}/update",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-hub-signature-256": f"sha256={hex_dig}",
            },
        )

    def test_inbound_creates_livechat_channel(self):
        """Incoming WhatsApp messages should create livechat channels when
        the gateway has a linked livechat channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel = self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", self.gateway.id),
                ("channel_type", "=", "livechat"),
            ]
        )
        self.assertTrue(channel, "A livechat channel should have been created")
        self.assertEqual(channel.livechat_channel_id, self.livechat_channel)
        self.assertTrue(channel.livechat_active)
        self.assertEqual(channel.gateway_channel_token, "34600000000")
        self.assertTrue(channel.message_ids)

    def test_inbound_operator_assigned(self):
        """The operator should be assigned from the livechat channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel = self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", self.gateway.id),
                ("channel_type", "=", "livechat"),
            ]
        )
        self.assertEqual(
            channel.livechat_operator_id,
            self.operator_user.partner_id,
        )

    def test_inbound_channel_reuse(self):
        """Subsequent messages from the same phone should reuse the channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel_1 = self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", self.gateway.id),
                ("channel_type", "=", "livechat"),
            ]
        )
        # Send another message from the same number
        second_message = dict(self.wa_message)
        second_message["entry"][0]["changes"][0]["value"]["messages"] = [
            {
                "from": "34600000000",
                "id": "wamid.TEST456",
                "timestamp": "1700000100",
                "text": {"body": "Second message"},
                "type": "text",
            }
        ]
        self._send_webhook_message(second_message)
        channels = self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", self.gateway.id),
                ("channel_type", "=", "livechat"),
            ]
        )
        self.assertEqual(len(channels), 1, "Should reuse existing channel")
        self.assertEqual(channels, channel_1)

    def test_outbound_sends_via_whatsapp(self):
        """Messages posted by operators in livechat channels linked to WhatsApp
        should be sent via the WhatsApp gateway."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel = self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", self.gateway.id),
                ("channel_type", "=", "livechat"),
            ]
        )
        with patch("requests.post") as post_mock:
            response_mock = MagicMock()
            response_mock.status_code = 200
            response_mock.json.return_value = {
                "messages": [{"id": "wamid.OUTBOUND123"}]
            }
            post_mock.return_value = response_mock
            channel.with_user(self.operator_user).message_post(
                body="Hello from operator",
                message_type="comment",
            )
            post_mock.assert_called()
            # Verify the WhatsApp API was called for sending
            wa_calls = [c for c in post_mock.call_args_list if "messages" in str(c)]
            self.assertTrue(wa_calls, "WhatsApp send API should have been called")

    def test_default_gateway_without_livechat(self):
        """When the gateway has no linked livechat channel, the default
        gateway behavior should be used (channel_type='gateway')."""
        # Create a gateway WITHOUT livechat
        plain_gateway = self.env["mail.gateway"].create(
            {
                "name": "Plain WA",
                "gateway_type": "whatsapp",
                "token": "plain_token",
                "whatsapp_security_key": "plain_key",
                "webhook_secret": "PLAIN-SECRET",
                "member_ids": [(4, self.operator_user.id)],
            }
        )
        plain_gateway.webhook_key = "plain_hook"
        plain_gateway.set_webhook()
        self.url_open(
            f"/gateway/{plain_gateway.gateway_type}"
            f"/{plain_gateway.webhook_key}"
            f"/update?hub.verify_token={plain_gateway.whatsapp_security_key}"
            f"&hub.challenge=22",
        )
        plain_message = dict(self.wa_message)
        data = json.dumps(plain_message)
        hex_dig = hmac.new(
            plain_gateway.webhook_secret.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.url_open(
            f"/gateway/{plain_gateway.gateway_type}"
            f"/{plain_gateway.webhook_key}/update",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-hub-signature-256": f"sha256={hex_dig}",
            },
        )
        channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", plain_gateway.id)]
        )
        self.assertTrue(channel)
        self.assertEqual(channel.channel_type, "gateway")
