# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from ast import literal_eval
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WhatsappNotificationRule(models.Model):
    """Configuration binding a WhatsApp template to any Odoo model.

    Other addons enqueue notifications through ``whatsapp.notification``
    using the technical ``event_key``; the matching rules decide which
    template, recipient and schedule apply. Nothing is hard coded to a
    particular business model, so the addon can serve any Odoo module.
    """

    _name = "whatsapp.notification.rule"
    _description = "WhatsApp Template Notification Rule"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    event_key = fields.Char(
        required=True,
        index=True,
        help="Technical key used by other addons to enqueue notifications, "
        "e.g. 'clinical_appointment_confirmation'.",
    )
    model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        domain=[("transient", "=", False)],
        help="Any Odoo model whose records should trigger a notification.",
    )
    model = fields.Char(related="model_id.model", store=True, readonly=True)
    template_id = fields.Many2one(
        "mail.whatsapp.template",
        ondelete="set null",
        domain="[('state', '=', 'approved')]",
        help="Approved Meta WhatsApp template used to render the message. "
        "Rules left without a template are ignored until configured.",
    )
    gateway_id = fields.Many2one(
        "mail.gateway", related="template_id.gateway_id", store=True, readonly=True
    )
    recipient_field = fields.Char(
        required=True,
        default="partner_id",
        help="Name of a res.partner Many2one field on the source model.",
    )
    phone_field = fields.Char(
        required=True,
        default="mobile",
        help="Name of the phone field on res.partner (for instance mobile).",
    )
    date_field = fields.Char(
        help="Date/Datetime field on the source model used to compute the "
        "scheduled date. Leave empty to send as soon as possible.",
    )
    offset_days = fields.Integer(default=0)
    offset_hours = fields.Float(default=0.0)
    auto_schedule = fields.Boolean(
        default=False,
        help="Let the cron scan this model and enqueue notifications "
        "automatically for the records matching the domain.",
    )
    domain = fields.Char(
        default="[]",
        help="Python literal domain used by the cron and by 'Schedule Now'.",
    )
    max_records = fields.Integer(default=100)
    max_retries = fields.Integer(default=3)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company.id
    )
    notification_ids = fields.One2many(
        "whatsapp.notification", "rule_id", string="Scheduled Notifications"
    )

    _sql_constraints = [
        (
            "event_key_model_company_uniq",
            "unique(event_key, model_id, company_id)",
            "Only one rule per event key, model and company is allowed.",
        ),
    ]

    @api.constrains("model_id", "recipient_field", "phone_field", "date_field")
    def _check_field_names(self):
        for rule in self:
            source_fields = self.env[rule.model]._fields
            if rule.recipient_field not in source_fields:
                raise ValidationError(
                    self.env._(
                        "The recipient field '%s' does not exist on the source model.",
                        rule.recipient_field,
                    )
                )
            if rule.phone_field not in self.env["res.partner"]._fields:
                raise ValidationError(
                    self.env._(
                        "The phone field '%s' does not exist on res.partner.",
                        rule.phone_field,
                    )
                )
            if rule.date_field and rule.date_field not in source_fields:
                raise ValidationError(
                    self.env._(
                        "The date field '%s' does not exist on the source model.",
                        rule.date_field,
                    )
                )

    def _compute_scheduled_date(self, record):
        """Return the send date for ``record`` (source date plus offsets)."""
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.date_field or self.date_field not in record._fields:
            scheduled = now
        else:
            scheduled = fields.Datetime.to_datetime(record[self.date_field]) or now
        return scheduled + timedelta(days=self.offset_days, hours=self.offset_hours)

    def _get_partner(self, record):
        """Resolve the res.partner that will receive the WhatsApp message."""
        self.ensure_one()
        if self.recipient_field in record._fields:
            partner = record[self.recipient_field]
            if partner._name == "res.partner":
                return partner
        if "partner_id" in record._fields:
            return record.partner_id
        return self.env["res.partner"]

    def _get_records_to_schedule(self):
        """Return the source records matching the rule domain."""
        self.ensure_one()
        if not self.model:
            return self.env["res.partner"]
        try:
            domain = literal_eval(self.domain or "[]")
        except (ValueError, SyntaxError, TypeError):
            _logger.warning(
                "Invalid domain on WhatsApp notification rule %s (%s)",
                self.name,
                self.id,
            )
            return self.env[self.model]
        if not isinstance(domain, list):
            return self.env[self.model]
        if self.date_field:
            domain = domain + [(self.date_field, "!=", False)]
        return self.env[self.model].search(domain, limit=self.max_records or 100)

    def action_schedule(self):
        """Enqueue notifications now for the records matching the domain."""
        for rule in self:
            records = rule._get_records_to_schedule()
            if records:
                self.env["whatsapp.notification"].schedule(rule.event_key, records)
        return True

    @api.model
    def _cron_schedule_notifications(self):
        """Ask every auto-scheduled rule to enqueue its pending records."""
        rules = self.search([("active", "=", True), ("auto_schedule", "=", True)])
        for rule in rules:
            try:
                with self.env.cr.savepoint():
                    rule.action_schedule()
            except Exception:  # pylint: disable=broad-except
                _logger.exception(
                    "Could not auto-schedule WhatsApp notification rule %s (%s)",
                    rule.name,
                    rule.id,
                )
        return True
