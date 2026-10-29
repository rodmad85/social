# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import copy
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
        second_message = copy.deepcopy(self.wa_message)
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

    # ------------------------------------------------------------------
    # Chatbot helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _mock_whatsapp_send(post_mock, message_id="wamid.BOT123"):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"messages": [{"id": message_id}]}
        post_mock.return_value = response

    @staticmethod
    def _whatsapp_payloads(post_mock):
        return [
            call.kwargs.get("json")
            for call in post_mock.call_args_list
            if isinstance(call.kwargs.get("json"), dict)
        ]

    @classmethod
    def _create_chatbot_script(cls):
        """A scripted flow: welcome text + one question with 3 options."""
        script = cls.env["chatbot.script"].create({"title": "WhatsApp Test Bot"})
        cls.env["chatbot.script.step"].create(
            {
                "chatbot_script_id": script.id,
                "step_type": "text",
                "message": "Bem vindo(a)! Aqui voce confirma sua consulta.",
            }
        )
        cls.env["chatbot.script.step"].create(
            {
                "chatbot_script_id": script.id,
                "step_type": "question_selection",
                "message": "Voce tem consulta marcada hoje, deseja confirmar?",
                "answer_ids": [
                    (0, 0, {"name": "Sim"}),
                    (0, 0, {"name": "Remarcar"}),
                    (0, 0, {"name": "Cancelar"}),
                ],
            }
        )
        return script

    def _start_chatbot_conversation(self, script):
        """First contact: returns the conversation with the bot waiting."""
        self.livechat_channel.whatsapp_chatbot_script_id = script
        self._setup_webhook()
        with patch("requests.post") as post_mock:
            self._mock_whatsapp_send(post_mock)
            self._send_webhook_message(self.wa_message)
            self.first_contact_payloads = self._whatsapp_payloads(post_mock)
        self.env.invalidate_all()
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertTrue(conversation, "The conversation must be created")
        return conversation

    def test_chatbot_first_contact_sends_interactive_question(self):
        """On the first WhatsApp contact the bot posts the scripted welcome
        steps and sends the question as WhatsApp interactive buttons."""
        script = self._create_chatbot_script()
        conversation = self._start_chatbot_conversation(script)
        self.assertTrue(
            conversation.chatbot_current_step_id,
            "The bot must be waiting for the customer's answer",
        )
        bot_messages = conversation.message_ids.filtered(
            lambda m: m.author_id == script.operator_partner_id
        )
        self.assertTrue(bot_messages, "The scripted messages must be posted")
        bodies = "\n".join(m.body or "" for m in bot_messages)
        self.assertIn("deseja confirmar", bodies)
        interactive = [
            payload
            for payload in self.first_contact_payloads
            if payload.get("type") == "interactive"
        ]
        self.assertEqual(
            len(interactive),
            1,
            "The question must be sent as a WhatsApp interactive message",
        )
        action = interactive[0]["interactive"]
        self.assertEqual(action["type"], "button")
        self.assertIn("deseja confirmar", action["body"]["text"])
        answers = conversation.chatbot_current_step_id.answer_ids
        self.assertEqual(len(action["action"]["buttons"]), 3)
        self.assertEqual(
            [button["reply"]["id"] for button in action["action"]["buttons"]],
            [f"wa_ans_{answer.id}" for answer in answers],
        )
        self.assertEqual(
            [button["reply"]["title"] for button in action["action"]["buttons"]],
            [answer.name for answer in answers],
        )
        # the conversation is mirrored on the gateway channel for attendants
        gateway_channel = self._gateway_channel(self.gateway)
        gateway_bodies = "\n".join(m.body or "" for m in gateway_channel.message_ids)
        self.assertIn("deseja confirmar", gateway_bodies)

    def test_chatbot_button_reply_ends_script(self):
        """A tap on an option is recorded, drives the script and stops it when
        there is no further step (the attendant takes over)."""
        script = self._create_chatbot_script()
        conversation = self._start_chatbot_conversation(script)
        step = conversation.chatbot_current_step_id
        answer = step.answer_ids[1]
        reply = copy.deepcopy(self.wa_message)
        reply["entry"][0]["changes"][0]["value"]["messages"] = [
            {
                "from": "34600000000",
                "id": "wamid.BTN1",
                "timestamp": "1700000200",
                "type": "button",
                "button": {"text": answer.name, "payload": f"wa_ans_{answer.id}"},
            }
        ]
        with patch("requests.post") as post_mock:
            self._mock_whatsapp_send(post_mock)
            self._send_webhook_message(reply)
        self.env.invalidate_all()
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        bodies = [m.body or "" for m in conversation.message_ids]
        self.assertTrue(
            any(answer.name in body for body in bodies),
            "The chosen option must be visible in the conversation",
        )
        self.assertFalse(
            conversation.chatbot_current_step_id,
            "The script must stop when it has no further step",
        )
        # the customer's choice is also visible on the gateway channel
        gateway_channel = self._gateway_channel(self.gateway)
        gateway_bodies = "\n".join(m.body or "" for m in gateway_channel.message_ids)
        self.assertIn(answer.name, gateway_bodies)

    def test_chatbot_typed_reply_asks_question_again(self):
        """Typing anything else than an option re-sends the question with its
        options instead of skipping the script."""
        script = self._create_chatbot_script()
        conversation = self._start_chatbot_conversation(script)
        with patch("requests.post") as post_mock:
            self._mock_whatsapp_send(post_mock)
            self._send_webhook_message(self._second_wa_message())
            payloads = self._whatsapp_payloads(post_mock)
        self.env.invalidate_all()
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertEqual(len(conversation), 1)
        self.assertTrue(
            conversation.chatbot_current_step_id,
            "The bot must still be waiting for a valid option",
        )
        interactive = [p for p in payloads if p.get("type") == "interactive"]
        self.assertEqual(
            len(interactive),
            1,
            "The question must be sent again as interactive buttons",
        )
        bot_messages = conversation.message_ids.filtered(
            lambda m: m.author_id == script.operator_partner_id
        )
        self.assertGreaterEqual(
            len(bot_messages),
            2,
            "The welcome and the repeated question must both be posted",
        )

    def test_chatbot_stops_when_attendant_replies(self):
        """Replying on the livechat conversation hands the chat over to the
        attendant: the bot stops talking."""
        script = self._create_chatbot_script()
        conversation = self._start_chatbot_conversation(script)
        self.assertTrue(conversation.chatbot_current_step_id)
        with patch("requests.post") as post_mock:
            self._mock_whatsapp_send(post_mock)
            conversation.with_user(self.operator_user).message_post(
                body="Oi! Aqui e a atendente",
                message_type="comment",
            )
        self.env.invalidate_all()
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertFalse(
            conversation.chatbot_current_step_id,
            "The bot must stop once a human replies",
        )

    def test_gateway_channel_reply_is_sent_and_stops_bot(self):
        """Attendants usually answer on the gateway (bot) channel: those
        messages are sent to the customer and stop the scripted bot."""
        script = self._create_chatbot_script()
        conversation = self._start_chatbot_conversation(script)
        self.assertTrue(conversation.chatbot_current_step_id)
        gateway_channel = self._gateway_channel(self.gateway)
        with patch("requests.post") as post_mock:
            self._mock_whatsapp_send(post_mock, message_id="wamid.ADMIN1")
            gateway_channel.with_user(self.admin_user).message_post(
                body="Falo com o cliente",
                message_type="comment",
            )
            wa_calls = [
                payload
                for payload in self._whatsapp_payloads(post_mock)
                if "Falo com o cliente" in str(payload)
            ]
        self.assertEqual(
            len(wa_calls),
            1,
            "A message posted on the gateway channel must reach WhatsApp",
        )
        self.env.invalidate_all()
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertFalse(
            conversation.chatbot_current_step_id,
            "The bot must stop when an attendant answers on the gateway channel",
        )

    def test_chatbot_not_configured_keeps_plain_flow(self):
        """Without a script on the livechat channel no bot message is sent."""
        self._setup_webhook()
        with patch("requests.post") as post_mock:
            self._mock_whatsapp_send(post_mock)
            self._send_webhook_message(self.wa_message)
            payloads = self._whatsapp_payloads(post_mock)
        self.env.invalidate_all()
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertTrue(conversation)
        self.assertFalse(conversation.chatbot_current_step_id)
        self.assertFalse(
            [p for p in payloads if p.get("type") == "interactive"],
            "No interactive message should be sent without a script",
        )

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

    def test_inbound_without_online_operator(self):
        """Conversations are created even when nobody is online: the operator
        of the livechat channel is used as a (offline) fallback."""
        self._setup_webhook()
        with patch.object(
            type(self.livechat_channel), "_get_operator", return_value=False
        ):
            self._send_webhook_message(self.wa_message)
        conversation = self._conversation_channel(self.livechat_channel, "34600000000")
        self.assertTrue(
            conversation,
            "Conversation must be created when no operator is online",
        )
        self.assertEqual(conversation.livechat_operator_id, self.operator_user.partner_id)
        members = conversation.channel_member_ids.mapped("partner_id")
        self.assertIn(self.operator_user.partner_id, members)
        self.assertIn(self.admin_user.partner_id, members, "Gateway members answer")
        bodies = [m.body or "" for m in conversation.message_ids]
        self.assertTrue(any("Hello from WhatsApp" in body for body in bodies))

    def test_inbound_channel_without_operators(self):
        """A livechat channel without configured operators still works: the
        gateway members are used as fallback operators."""
        gateway = self.env["mail.gateway"].create(
            {
                "name": "No Op Gateway",
                "gateway_type": "whatsapp",
                "token": "noop_token",
                "whatsapp_security_key": "noop_key",
                "webhook_secret": "NOOP-SECRET",
                "member_ids": [(4, self.admin_user.id)],
            }
        )
        livechat_channel = self.env["im_livechat.channel"].create(
            {
                "name": "WA without operators",
                "whatsapp_gateway_id": gateway.id,
                "user_ids": [Command.clear()],
            }
        )
        self.assertFalse(livechat_channel.user_ids)
        self._setup_webhook(gateway)
        with patch.object(type(livechat_channel), "_get_operator", return_value=False):
            self._send_webhook_message(self.wa_message, gateway=gateway)
        conversation = self._conversation_channel(livechat_channel, "34600000000")
        self.assertTrue(conversation, "Conversation must be created without operators")
        self.assertEqual(conversation.livechat_operator_id, self.admin_user.partner_id)
        self.assertIn(
            self.admin_user.partner_id,
            conversation.channel_member_ids.mapped("partner_id"),
        )

    def test_inbound_without_operator_and_without_members(self):
        """No operator on the channel and no member on the gateway: the
        conversation is still created (livechat requires an operator partner,
        so the module falls back to any livechat operator / admin)."""
        gateway = self.env["mail.gateway"].create(
            {
                "name": "Empty Gateway",
                "gateway_type": "whatsapp",
                "token": "empty_token",
                "whatsapp_security_key": "empty_key",
                "webhook_secret": "EMPTY-SECRET",
            }
        )
        livechat_channel = self.env["im_livechat.channel"].create(
            {
                "name": "WA empty",
                "whatsapp_gateway_id": gateway.id,
                "user_ids": [Command.clear()],
            }
        )
        self.assertFalse(gateway.member_ids)
        self.assertFalse(livechat_channel.user_ids)
        self._setup_webhook(gateway)
        with patch.object(type(livechat_channel), "_get_operator", return_value=False):
            self._send_webhook_message(self.wa_message, gateway=gateway)
        conversation = self._conversation_channel(livechat_channel, "34600000000")
        self.assertTrue(conversation, "Conversation must always be created")
        self.assertTrue(
            conversation.livechat_operator_id,
            "livechat_operator_id is required by the SQL constraint",
        )
        self.assertIn(
            conversation.livechat_operator_id,
            conversation.channel_member_ids.mapped("partner_id"),
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

    def test_admin_gateway_post_sent(self):
        """Attendants answer on the gateway (bot) channel: those messages are
        sent to the customer through WhatsApp (single send, no loop)."""
        self._setup_webhook()
        self._send_webhook_message(self.wa_message)
        gateway_channel = self._gateway_channel(self.gateway)
        with patch("requests.post") as post_mock:
            response_mock = MagicMock()
            response_mock.status_code = 200
            response_mock.json.return_value = {
                "messages": [{"id": "wamid.ADMIN"}]
            }
            post_mock.return_value = response_mock
            gateway_channel.with_user(self.admin_user).message_post(
                body="Admin note",
                message_type="comment",
            )
            wa_calls = [
                c
                for c in post_mock.call_args_list
                if "Admin note" in str(c.kwargs.get("json"))
            ]
        self.assertEqual(
            len(wa_calls),
            1,
            "A message posted on the gateway channel must be sent once",
        )

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
        livechat_before = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self._send_webhook_message(self.wa_message, gateway=plain_gateway)
        channel = self.env["discuss.channel"].search(
            [("gateway_id", "=", plain_gateway.id)]
        )
        self.assertTrue(channel)
        self.assertEqual(channel.channel_type, "gateway")
        livechat_after = self.env["discuss.channel"].search(
            [("channel_type", "=", "livechat")]
        )
        self.assertEqual(
            livechat_before,
            livechat_after,
            "No livechat conversation should be created without a linked channel",
        )

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