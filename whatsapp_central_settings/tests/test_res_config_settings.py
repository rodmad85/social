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
            "wa_call_provider_user_ids",
            "wa_call_default_provider_user_ids",
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

    def test_03_onchange_with_saved_many2many(self):
        """Carregar as configurações com many2many já salvos não deve falhar.

        Regressão: get_values() retornava uma lista simples de ids para os
        campos many2many e o onchange quebrava com
        "TypeError: 'int' object is not subscriptable".
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "whatsapp_central_settings.wa_call_make_user_ids",
            str(self.env.user.id),
        )
        fields_spec = {
            "wa_call_make_user_ids": {"fields": {"display_name": {}}},
            "wa_unassigned_action": {},
        }
        result = self.settings.onchange({}, [], fields_spec)
        self.assertIn("value", result)
        self.assertIn("wa_call_make_user_ids", result["value"])

    def test_04_provider_fields_saved_as_params(self):
        """Allowed/Default Provider devem ser persistidos em parâmetros."""
        ICPSudo = self.env["ir.config_parameter"].sudo()
        settings = self.settings.create(
            {
                "wa_call_provider_user_ids": [(6, 0, [self.env.user.id])],
                "wa_call_default_provider_user_ids": [(6, 0, [self.env.user.id])],
            }
        )
        settings.set_values()
        self.assertEqual(
            ICPSudo.get_param("whatsapp_central_settings.wa_call_provider_user_ids"),
            str(self.env.user.id),
        )
        self.assertEqual(
            ICPSudo.get_param(
                "whatsapp_central_settings.wa_call_default_provider_user_ids"
            ),
            str(self.env.user.id),
        )

    def test_05_sync_provider_fields_without_calling_module(self):
        """Sem o módulo de chamada, o sync não deve levantar exceção."""
        settings = self.settings.create(
            {
                "wa_call_provider_user_ids": [(6, 0, [self.env.user.id])],
                "wa_call_default_provider_user_ids": [(6, 0, [self.env.user.id])],
            }
        )
        has_provider_fields = (
            "provider_id" in self.env["res.users"]._fields
            and "provider_ids" in self.env["res.users"]._fields
        )
        settings._sync_call_provider_fields()
        if not has_provider_fields:
            self.assertFalse(self.env.user.provider_id)
