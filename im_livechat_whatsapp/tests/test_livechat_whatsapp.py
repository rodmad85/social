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

    def _gateway_channel(self, gateway):
        return self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", gateway.id),
                ("channel_type", "=", "gateway"),
            ],
            limit=1,
        )

    def _conversation_channel(self, livechat_channel, token):
        return self.env["discuss.channel"].search(
            [
                ("channel_type", "=", "livechat"),
                ("livechat_channel_id", "=", livechat_channel.id),
                ("gateway_channel_token", "=", token),
            ],
            limit=1,
        )

    def _second_wa_message(self):
        """A second message from the same WhatsApp number."""
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
        return second_message

    def test_inbound_creates_two_channels(self):
        """Incoming WhatsApp messages create a gateway (bot) channel and a
        mirrored livechat conversation channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        gateway_channel = self._gateway_channel(self.gateway)
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertTrue(gateway_channel, "A gateway channel should exist")
        self.assertTrue(conversation, "A livechat conversation should exist")
        self.assertEqual(conversation.livechat_channel_id, self.livechat_channel)
        self.assertTrue(conversation.livechat_active)
        self.assertEqual(conversation.gateway_channel_token, "34600000000")
        self.assertTrue(conversation.message_ids)
        bodies = [m.body or "" for m in conversation.message_ids]
        self.assertTrue(
            any("Hello from WhatsApp" in body for body in bodies),
            "Message should be mirrored in the livechat conversation",
        )

    def test_inbound_operator_assigned(self):
        """The operator should be assigned from the livechat channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertEqual(
            conversation.livechat_operator_id,
            self.operator_user.partner_id,
        )

    def test_inbound_channel_reuse(self):
        """Subsequent messages from the same phone should reuse both channels."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        gateway_channel_1 = self._gateway_channel(self.gateway)
        conversation_1 = self._conversation_channel(self.livechat_channel, "34600000000")
        # Send another message from the same number
        self._send_webhook_message(self._second_wa_message())
        gateway_channel = self.env["discuss.channel"].search(
            [
                ("gateway_id", "=", self.gateway.id),
                ("channel_type", "=", "gateway"),
            ]
        )
        conversation = self.env["discuss.channel"].search(
            [
                ("channel_type", "=", "livechat"),
                ("livechat_channel_id", "=", self.livechat_channel.id),
                ("gateway_channel_token", "=", "34600000000"),
            ]
        )
        self.assertEqual(len(gateway_channel), 1, "Should reuse gateway channel")
        self.assertEqual(len(conversation), 1, "Should reuse livechat conversation")
        self.assertEqual(gateway_channel, gateway_channel_1)
        self.assertEqual(conversation, conversation_1)

    def test_outbound_sends_via_whatsapp_once(self):
        """Operator replies on the livechat conversation are sent through
        WhatsApp exactly once and mirrored into the bot channel."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        gateway_channel = self._gateway_channel(self.gateway)
        with patch("requests.post") as post_mock:
            response_mock = MagicMock()
            response_mock.status_code = 200
            response_mock.json.return_value = {
                "messages": [{"id": "wamid.OUTBOUND123"}]
            }
            post_mock.return_value = response_mock
            message = conversation.with_user(self.operator_user).message_post(
                body="Hello from operator",
                message_type="comment",
            )
            wa_calls = [c for c in post_mock.call_args_list if "messages" in str(c)]
            self.assertEqual(
                len(wa_calls), 1, "The WhatsApp send API should be called once"
            )
            notification = self.env["mail.notification"].search(
                [
                    ("gateway_channel_id", "=", gateway_channel.id),
                    ("mail_message_id", "=", message.id),
                ]
            )
            self.assertTrue(notification, "A gateway notification should exist")
            self.assertEqual(notification.gateway_message_id, "wamid.OUTBOUND123")
        bodies = [m.body or "" for m in gateway_channel.message_ids]
        self.assertTrue(
            any("Hello from operator" in body for body in bodies),
            "Reply should be mirrored into the bot channel",
        )

    def test_admin_gateway_post_not_sent(self):
        """Messages posted on the bot channel are not sent via WhatsApp: only
        livechat operators send messages."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        gateway_channel = self._gateway_channel(self.gateway)
        with patch("requests.post") as post_mock:
            gateway_channel.with_user(self.admin_user).message_post(
                body="Admin note",
                message_type="comment",
            )
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
        channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", plain_gateway.id)]
        )
        self.assertTrue(channel)
        self.assertEqual(channel.channel_type, "gateway")
        conversation = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self.assertFalse(conversation)

    def test_preexisting_gateway_channel_gets_livechat_partner(self):
        """An existing gateway conversation gets a livechat peer when the
        gateway is later linked to a livechat channel."""
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
        gateway_channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", plain_gateway.id)]
        )
        self.assertTrue(gateway_channel)
        self.assertEqual(gateway_channel.channel_type, "gateway")
        # Link the gateway to a livechat channel now
        livechat_channel = self.env["im_livechat.channel"].create(
            {
                "name": "WhatsApp Support 2",
                "user_ids": [(4, self.operator_user.id)],
                "whatsapp_gateway_id": plain_gateway.id,
            }
        )
        # A new message from the same number should create the conversation peer
        self._send_webhook_message(self._second_wa_message(), gateway=plain_gateway)
        conversation = self._conversation_channel(livechat_channel, "34600000000")
        self.assertTrue(conversation, "Livechat peer should be created")
        gateway_channels = self.env["discuss.channel"].search(
            [("gateway_id", "=", plain_gateway.id)]
        )
        self.assertEqual(len(gateway_channels), 1, "Gateway channel should be reused")