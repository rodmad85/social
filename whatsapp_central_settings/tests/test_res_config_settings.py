# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestWhatsAppCentralSettings(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env["res.config.settings"]

    def test_01_settings_fields_exist(self):
        """As 5 configurações do WhatsApp devem existir no res.config.settings."""
        expected_fields = [
            "wa_call_receive_user_ids",
            "wa_call_make_user_ids",
            "wa_template_edit_user_ids",
            "wa_unassigned_action",
            "wa_unassigned_user_id",
            "wa_conversation_menu_group_ids",
        ]
        for fname in expected_fields:
            self.assertIn(
                fname,
                self.settings._fields,
                "O campo %s não existe em res.config.settings." % fname,
            )

    def test_02_unassigned_action_default(self):
        """O valor padrão de mensagens não atribuídas deve ser 'list'."""
        settings = self.settings.create({})
        self.assertEqual(settings.wa_unassigned_action, "list")
