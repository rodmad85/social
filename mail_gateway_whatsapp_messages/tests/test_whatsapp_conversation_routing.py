# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("-at_install", "post_install")
class TestWhatsAppConversationRouting(TransactionCase):
    """Roteamento das conversas WhatsApp para o usuário responsável."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gateway = cls.env["mail.gateway"].create(
            {
                "name": "Test WhatsApp Gateway",
                "gateway_type": "whatsapp",
                "token": "test-wa-token",
                "whatsapp_security_key": "key",
                "webhook_secret": "secret",
                "member_ids": [Command.set([cls.env.user.id])],
            }
        )
        cls.contact = cls.env["res.partner"].create(
            {"name": "Contato WhatsApp", "phone": "+5511999999999"}
        )
        cls.gateway_user = cls.env["res.users"].create(
            {
                "name": "Usuário Gateway",
                "login": "wa_gateway_test_user",
                "email": "wa_gateway_test_user@example.com",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("mail_gateway.gateway_user").id,
                        ]
                    )
                ],
            }
        )

    def _update(self, phone="5511999999999", name="Contato WhatsApp"):
        return {
            "contacts": [{"wa_id": phone, "profile": {"name": name}}],
            "messages": [{"from": phone}],
        }

    def _create_channel(self, token="5511999999999", name="Contato"):
        return self.env["discuss.channel"].create(
            {
                "name": name,
                "channel_type": "gateway",
                "gateway_id": self.gateway.id,
                "gateway_channel_token": token,
            }
        )

    def _set_unassigned_settings(self, action, user=None):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("whatsapp_central_settings.wa_unassigned_action", action)
        params.set_param(
            "whatsapp_central_settings.wa_unassigned_user_id",
            str(user.id) if user else "",
        )

    def _internal_members(self, channel):
        return channel.channel_member_ids.filtered(
            lambda member: member.partner_id.user_ids.filtered("active")
        )

    def test_01_new_channel_does_not_include_gateway_members(self):
        """Canal novo não deve trazer os usuários do gateway como membros."""
        channel = self.env["mail.gateway.whatsapp"]._get_channel(
            self.gateway, "5511999999999", self._update(), force_create=True
        )
        self.assertTrue(channel)
        self.assertFalse(
            self._internal_members(channel),
            "Nenhum usuário interno deve ser adicionado automaticamente.",
        )

    def test_02_assign_action_adds_default_user(self):
        """Com a opção 'assign', a conversa vai para o usuário padrão."""
        self._set_unassigned_settings("assign", self.gateway_user)
        channel = self._create_channel()
        self.env["mail.gateway.whatsapp"]._assign_default_user(channel)
        self.assertIn(
            self.gateway_user.partner_id,
            channel.channel_member_ids.partner_id,
        )

    def test_03_list_action_keeps_conversation_unassigned(self):
        """Com a opção 'list', ninguém é adicionado automaticamente."""
        self._set_unassigned_settings("list")
        channel = self._create_channel()
        self.env["mail.gateway.whatsapp"]._assign_default_user(channel)
        self.assertFalse(self._internal_members(channel))

    def test_04_existing_member_is_not_replaced(self):
        """Conversa já iniciada/atribuída não recebe o usuário padrão."""
        self._set_unassigned_settings("assign", self.gateway_user)
        channel = self._create_channel()
        self.env["discuss.channel.member"].create(
            {
                "channel_id": channel.id,
                "partner_id": self.env.user.partner_id.id,
                "unpin_dt": False,
            }
        )
        self.env["mail.gateway.whatsapp"]._assign_default_user(channel)
        self.assertNotIn(
            self.gateway_user.partner_id,
            channel.channel_member_ids.partner_id,
        )
        self.assertIn(
            self.env.user.partner_id,
            channel.channel_member_ids.partner_id,
        )

    def test_05_conversation_view_uses_channel_id(self):
        """A view deve ter id estável (channel_id) e última mensagem."""
        channel = self._create_channel()
        self.env["mail.message"].create(
            {
                "model": "discuss.channel",
                "res_id": channel.id,
                "body": "Mensagem de teste",
                "message_type": "comment",
                "gateway_type": "whatsapp",
                "author_id": self.contact.id,
            }
        )
        conversation = self.env["mail.whatsapp.conversation"].search(
            [("channel_id", "=", channel.id)]
        )
        self.assertEqual(len(conversation), 1)
        self.assertEqual(conversation.id, channel.id)
        self.assertEqual(conversation.last_message_body, "Mensagem de teste")
        self.assertEqual(conversation.message_count, 1)
        self.assertTrue(conversation.is_unassigned)

    def test_06_claim_adds_current_user(self):
        """Assumir a conversa adiciona o usuário atual e abre o Discuss."""
        channel = self._create_channel()
        self.env["mail.message"].create(
            {
                "model": "discuss.channel",
                "res_id": channel.id,
                "body": "Mensagem de teste",
                "message_type": "comment",
                "gateway_type": "whatsapp",
                "author_id": self.contact.id,
            }
        )
        conversation = self.env["mail.whatsapp.conversation"].search(
            [("channel_id", "=", channel.id)]
        )
        action = conversation.action_claim()
        self.assertEqual(action["tag"], "mail.action_discuss")
        self.assertIn(
            self.env.user.partner_id,
            channel.channel_member_ids.partner_id,
        )
