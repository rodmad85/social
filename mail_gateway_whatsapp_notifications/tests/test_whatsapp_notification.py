# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


def _raise_boom(record):  # pylint: disable=unused-argument
    # A plain exception is enough to exercise the retry path; no user-facing
    # string is involved here.
    raise RuntimeError("boom")


@tagged("post_install", "-at_install")
class TestWhatsappNotification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gateway = cls.env["mail.gateway"].create(
            {
                "name": "Test WhatsApp Gateway",
                "token": "test-whatsapp-notifications-token",
                "gateway_type": "whatsapp",
            }
        )
        cls.partner_model_id = cls.env["ir.model"]._get_id("res.partner")
        cls.template = cls.env["mail.whatsapp.template"].create(
            {
                "name": "Test Notification Template",
                "body": "Hello {{1}}",
                "category": "utility",
                "language": "en",
                "state": "approved",
                "gateway_id": cls.gateway.id,
                "model_id": cls.partner_model_id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Patient", "mobile": "+55 11 99999-9999"}
        )

    def _create_rule(self, **kwargs):
        vals = {
            "name": "Test Rule",
            "event_key": "test_event",
            "model_id": self.partner_model_id,
            "template_id": self.template.id,
            "recipient_field": "commercial_partner_id",
            "phone_field": "mobile",
            "date_field": "create_date",
            "offset_days": -1,
            "max_retries": 3,
        }
        vals.update(kwargs)
        return self.env["whatsapp.notification.rule"].create(vals)

    def _notifications_for(self, event_key="test_event"):
        return self.env["whatsapp.notification"].search([("event_key", "=", event_key)])

    def test_schedule_creates_a_pending_notification(self):
        rule = self._create_rule()
        notifications = self.env["whatsapp.notification"].schedule(
            "test_event", self.partner
        )
        self.assertEqual(len(notifications), 1)
        notification = notifications
        self.assertEqual(notification.state, "pending")
        self.assertEqual(notification.rule_id, rule)
        self.assertEqual(notification.partner_id, self.partner)
        self.assertEqual(notification.template_id, self.template)
        self.assertEqual(notification.gateway_id, self.gateway)
        self.assertEqual(notification.res_model, "res.partner")
        self.assertEqual(notification.res_id, self.partner.id)
        expected = fields.Datetime.to_datetime(self.partner.create_date) + timedelta(
            days=-1
        )
        self.assertEqual(notification.scheduled_date, expected)

    def test_schedule_is_idempotent(self):
        self._create_rule()
        self.env["whatsapp.notification"].schedule("test_event", self.partner)
        second = self.env["whatsapp.notification"].schedule("test_event", self.partner)
        self.assertFalse(second)
        self.assertEqual(len(self._notifications_for()), 1)

    def test_schedule_without_rule_is_a_noop(self):
        result = self.env["whatsapp.notification"].schedule(
            "unknown_event", self.partner
        )
        self.assertFalse(result)
        self.assertFalse(self._notifications_for("unknown_event"))

    def test_rule_without_template_is_skipped(self):
        self._create_rule(template_id=False)
        result = self.env["whatsapp.notification"].schedule("test_event", self.partner)
        self.assertFalse(result)

    def test_invalid_recipient_field_raises(self):
        with self.assertRaises(ValidationError):
            self._create_rule(recipient_field="this_field_does_not_exist")

    def test_action_send_marks_notification_as_sent(self):
        self._create_rule()
        notification = self.env["whatsapp.notification"].schedule(
            "test_event", self.partner
        )
        self.patch(
            self.env.registry["whatsapp.notification"],
            "_send_whatsapp",
            lambda rec: rec.env["mail.message"],
        )
        notification.action_send()
        self.assertEqual(notification.state, "sent")
        self.assertTrue(notification.sent_date)
        self.assertFalse(notification.error_message)

    def test_action_send_retries_on_error(self):
        self._create_rule()
        notification = self.env["whatsapp.notification"].schedule(
            "test_event", self.partner
        )
        self.patch(
            self.env.registry["whatsapp.notification"],
            "_send_whatsapp",
            _raise_boom,
        )
        notification.action_send()
        self.assertEqual(notification.state, "pending")
        self.assertEqual(notification.retry_count, 1)
        self.assertEqual(notification.error_message, "boom")

    @freeze_time("2026-01-10 08:00:00")
    def test_cron_sends_due_notifications(self):
        self._create_rule()
        notification = self.env["whatsapp.notification"].schedule(
            "test_event", self.partner, scheduled_date="2026-01-09 08:00:00"
        )
        self.patch(
            self.env.registry["whatsapp.notification"],
            "_send_whatsapp",
            lambda rec: rec.env["mail.message"],
        )
        self.env["whatsapp.notification"]._cron_process_notifications()
        self.assertEqual(notification.state, "sent")

    def test_cancel_and_reset(self):
        self._create_rule()
        notification = self.env["whatsapp.notification"].schedule(
            "test_event", self.partner
        )
        notification.action_cancel()
        self.assertEqual(notification.state, "cancelled")
        notification.action_reset()
        self.assertEqual(notification.state, "pending")
        self.assertEqual(notification.retry_count, 0)
