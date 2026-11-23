# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hashlib
import hmac
import json
from copy import deepcopy
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
                    Command.link(cls.env.ref("mail_gateway.gateway_user").id),
                ],
            }
        )
        # Create a gateway admin user (member of mail_gateway.gateway_user)
        cls.admin_user = cls.env["res.users"].create(
            {
                "name": "Gateway Admin",
                "login": "gateway_admin_wa",
                "password": "gateway_admin_wa",
                "groups_id": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("mail_gateway.gateway_user").id),
                ],
            }
        )
        # Make the operator available so livechat can assign it.
        cls.env["bus.presence"].create(
            {"user_id": cls.operator_user.id, "status": "online"}
        )
        # Create a WhatsApp gateway
        cls.gateway = cls.env["mail.gateway"].create(
            {
                "name": "WA Gateway",
                "gateway_type": "whatsapp",
                "token": "test_token",
                "whatsapp_security_key": "test_key",
                "webhook_secret": "MY-SECRET",
                "member_ids": [
                    (4, cls.operator_user.id),
                    (4, cls.admin_user.id),
                ],
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

    def _setup_webhook(self, gateway=False):
        """Helper to set up and integrate the webhook."""
        gateway = gateway or self.gateway
        gateway.webhook_key = "test_hook"
        gateway.set_webhook()
        self.url_open(
            f"/gateway/{gateway.gateway_type}/{gateway.webhook_key}"
            f"/update?hub.verify_token={gateway.whatsapp_security_key}"
            f"&hub.challenge=22",
        )
        self.assertEqual(gateway.integrated_webhook_state, "integrated")

    def _send_webhook_message(self, message, gateway=False):
        """Send a webhook message with proper HMAC signature."""
        gateway = gateway or self.gateway
        data = json.dumps(message)
        hex_dig = hmac.new(
            gateway.webhook_secret.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.url_open(
            f"/gateway/{gateway.gateway_type}"
            f"/{gateway.webhook_key}/update",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-hub-signature-256": f"sha256={hex_dig}",
            },
        )

    def _gateway_channels(self, gateway=None):
        gateway = gateway or self.gateway
        return self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", gateway.id),
                ("channel_type", "=", "gateway"),
            ]
        )

    def _second_wa_message(self):
        """A second message from the same WhatsApp number."""
        second_message = deepcopy(self.wa_message)
        second_message["entry"][0]["changes"][0]["value"]["messages"] = [
            {
                "from": "34600000000",
                "id": "wamid.TEST456",
                "timestamp": "1700000100",
                "text": {"body": "Second message"},
                "type": "text",
            }
        ]
        return second_message

    def test_inbound_creates_single_gateway_channel(self):
        """Incoming WhatsApp messages create a single gateway channel and no
        separate livechat conversation."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channels = self._gateway_channels()
        self.assertEqual(len(channels), 1, "A single gateway channel should exist")
        channel = channels
        self.assertEqual(channel.gateway_channel_token, "34600000000")
        self.assertEqual(channel.livechat_channel_id, self.livechat_channel)
        self.assertEqual(channel.name, "Test Visitor")
        self.assertEqual(channel.anonymous_name, "Test Visitor")
        self.assertTrue(channel.message_ids)
        bodies = [m.body or "" for m in channel.message_ids]
        self.assertTrue(
            any("Hello from WhatsApp" in body for body in bodies),
            "The inbound message should be stored on the gateway channel",
        )
        conversations = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self.assertFalse(conversations, "No livechat conversation should be created")

    def test_inbound_operator_assigned(self):
        """The operator configured on the linked livechat channel is stored on
        the gateway channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel = self._gateway_channels()
        self.assertEqual(
            channel.livechat_operator_id,
            self.operator_user.partner_id,
        )
        self.assertIn(
            self.operator_user.partner_id,
            channel.channel_member_ids.partner_id,
        )
        self.assertIn(
            self.admin_user.partner_id,
            channel.channel_member_ids.partner_id,
        )

    def test_inbound_registered_contact_uses_partner_name(self):
        """A contact registered in Odoo is displayed with its Odoo name."""
        partner = self.env["res.partner"].create(
            {"name": "Registered Contact", "phone": "+34600000000"}
        )
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel = self._gateway_channels()
        self.assertEqual(channel.name, partner.name)
        self.assertIn(partner, channel.channel_member_ids.partner_id)

    def test_inbound_channel_reuse(self):
        """Subsequent messages from the same phone reuse the gateway channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel_1 = self._gateway_channels()
        self._send_webhook_message(self._second_wa_message())
        channels = self._gateway_channels()
        self.assertEqual(len(channels), 1, "Should reuse the gateway channel")
        self.assertEqual(channels, channel_1)
        conversations = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self.assertFalse(conversations, "No livechat conversation should be created")

    def test_outbound_sends_via_whatsapp_once(self):
        """A reply on the gateway channel is sent through WhatsApp once."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        channel = self._gateway_channels()
        with patch("requests.post") as post_mock:
            response_mock = MagicMock()
            response_mock.status_code = 200
            response_mock.json.return_value = {
                "messages": [{"id": "wamid.OUTBOUND123"}]
            }
            post_mock.return_value = response_mock
            message = channel.with_user(self.operator_user).message_post(
                body="Hello from operator",
                message_type="comment",
            )
            wa_calls = [c for c in post_mock.call_args_list if "messages" in str(c)]
            self.assertEqual(
                len(wa_calls), 1, "The WhatsApp send API should be called once"
            )
            notification = self.env["mail.notification"].search(
                [
                    ("gateway_channel_id", "=", channel.id),
                    ("mail_message_id", "=", message.id),
                ]
            )
            self.assertTrue(notification, "A gateway notification should exist")
            self.assertEqual(notification.gateway_message_id, "wamid.OUTBOUND123")

    def test_inbound_message_not_sent_back(self):
        """Incoming messages are stored but never echoed back to WhatsApp."""
        with patch("requests.post") as post_mock:
            self._setup_webhook()
            self._send_webhook_message(self.wa_message)
            post_mock.assert_not_called()

    def test_default_gateway_without_livechat(self):
        """When the gateway has no linked livechat channel, the default
        gateway behavior should be used (channel_type='gateway')."""
        plain_gateway = self.env["mail.gateway"].create(
            {
                "name": "Plain WA",
                "gateway_type": "whatsapp",
                "token": "plain_token",
                "whatsapp_security_key": "plain_key",
                "webhook_secret": "PLAIN-SECRET",
                "member_ids": [
                    (4, self.admin_user.id),
                ],
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
        self._send_webhook_message(self.wa_message, gateway=plain_gateway)
        channel = self._gateway_channels(plain_gateway)
        self.assertTrue(channel)
        self.assertEqual(channel.channel_type, "gateway")
        self.assertFalse(channel.livechat_channel_id)
        conversations = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self.assertFalse(conversations)

    def test_preexisting_gateway_channel_reused_after_livechat_link(self):
        """When a gateway is linked to a livechat channel after a conversation
        already exists, that same gateway channel is reused."""
        plain_gateway = self.env["mail.gateway"].create(
            {
                "name": "Pre WA",
                "gateway_type": "whatsapp",
                "token": "pre_token",
                "whatsapp_security_key": "pre_key",
                "webhook_secret": "PRE-SECRET",
                "member_ids": [
                    (4, self.admin_user.id),
                ],
            }
        )
        plain_gateway.webhook_key = "pre_hook"
        plain_gateway.set_webhook()
        self.url_open(
            f"/gateway/{plain_gateway.gateway_type}"
            f"/{plain_gateway.webhook_key}"
            f"/update?hub.verify_token={plain_gateway.whatsapp_security_key}"
            f"&hub.challenge=22",
        )
        self._send_webhook_message(self.wa_message, gateway=plain_gateway)
        channel = self._gateway_channels(plain_gateway)
        self.assertTrue(channel)
        self.assertEqual(channel.channel_type, "gateway")
        # Link the gateway to a livechat channel now
        self.env["im_livechat.channel"].create(
            {
                "name": "WhatsApp Support 2",
                "user_ids": [(4, self.operator_user.id)],
                "whatsapp_gateway_id": plain_gateway.id,
            }
        )
        self._send_webhook_message(self._second_wa_message(), gateway=plain_gateway)
        channels = self._gateway_channels(plain_gateway)
        self.assertEqual(len(channels), 1, "Gateway channel should be reused")
        conversations = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self.assertFalse(conversations, "No livechat conversation should be created")
