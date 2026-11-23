# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WhatsappNotification(models.Model):
    """Queue/agenda of WhatsApp template messages waiting to be sent."""

    _name = "whatsapp.notification"
    _description = "Scheduled WhatsApp Template Notification"
    _order = "scheduled_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    rule_id = fields.Many2one(
        "whatsapp.notification.rule", ondelete="set null", index=True
    )
    event_key = fields.Char(required=True, index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Many2oneReference(
        string="Source Record ID", model_field="res_model", required=True, index=True
    )
    record_name = fields.Char(compute="_compute_record_name", store=False)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")
    phone_field = fields.Char(required=True, default="mobile")
    phone = fields.Char(readonly=True)
    template_id = fields.Many2one(
        "mail.whatsapp.template", required=True, ondelete="restrict"
    )
    gateway_id = fields.Many2one(
        "mail.gateway", related="template_id.gateway_id", store=True, readonly=True
    )
    scheduled_date = fields.Datetime(required=True, index=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("error", "Error"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    sent_date = fields.Datetime(readonly=True)
    message_id = fields.Many2one("mail.message", readonly=True, ondelete="set null")
    retry_count = fields.Integer(default=0, readonly=True)
    error_message = fields.Text(readonly=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company.id
    )

    @api.depends("event_key", "partner_id", "template_id")
    def _compute_name(self):
        for notification in self:
            notification.name = (
                f"{notification.event_key} / "
                f"{notification.partner_id.display_name or '-'} / "
                f"{notification.template_id.name or '-'}"
            )

    @api.depends("res_model", "res_id")
    def _compute_record_name(self):
        for notification in self:
            model = notification.res_model
            if not model or model not in self.env.registry:
                notification.record_name = False
                continue
            record = self.env[model].browse(notification.res_id).exists()
            notification.record_name = record.display_name if record else False

    @api.model
    def schedule(self, event_key, records, scheduled_date=None):
        """Enqueue WhatsApp template notifications for ``records``.

        Every active rule matching ``event_key`` and the records' model is
        evaluated. Rules without a configured template are skipped, so caller
        addons may invoke this method unconditionally without interrupting
        their own business flow. Returns the created notifications (possibly
        an empty recordset).
        """
        if not records:
            return self
        rules = self.env["whatsapp.notification.rule"].search(
            [
                ("event_key", "=", event_key),
                ("model", "=", records._name),
                ("active", "=", True),
                ("company_id", "in", [False, self.env.company.id]),
            ],
            order="sequence, id",
        )
        if not rules:
            _logger.debug(
                "No active WhatsApp notification rule for event %s on %s",
                event_key,
                records._name,
            )
            return self
        notifications = self
        for rule in rules:
            if not rule.template_id:
                _logger.debug(
                    "WhatsApp notification rule %s (%s) has no template; skipped",
                    rule.name,
                    rule.id,
                )
                continue
            for record in records:
                partner = rule._get_partner(record)
                if not partner:
                    _logger.debug(
                        "No partner found for %s,%s on rule %s",
                        records._name,
                        record.id,
                        rule.name,
                    )
                    continue
                existing = self.search(
                    [
                        ("rule_id", "=", rule.id),
                        ("res_model", "=", records._name),
                        ("res_id", "=", record.id),
                        ("state", "in", ["draft", "pending", "sent"]),
                    ],
                    limit=1,
                )
                if existing:
                    continue
                phone = (
                    partner[rule.phone_field]
                    if rule.phone_field in partner._fields
                    else False
                )
                notifications |= self.create(
                    {
                        "rule_id": rule.id,
                        "event_key": rule.event_key,
                        "res_model": records._name,
                        "res_id": record.id,
                        "partner_id": partner.id,
                        "phone_field": rule.phone_field,
                        "phone": phone,
                        "template_id": rule.template_id.id,
                        "scheduled_date": scheduled_date
                        or rule._compute_scheduled_date(record),
                        "state": "pending",
                        "company_id": rule.company_id.id or self.env.company.id,
                    }
                )
        return notifications

    def _send_whatsapp(self):
        """Render the template and post it on the WhatsApp gateway channel.

        This mirrors the canonical API of ``whatsapp.composer`` from
        ``mail_gateway_whatsapp``: a ``message_post`` on the gateway channel
        with ``whatsapp_template_id`` in the context triggers the gateway
        ``mail.notification`` and the Meta template send.
        """
        self.ensure_one()
        template = self.template_id
        gateway = self.gateway_id
        partner = self.partner_id
        phone_field = self.phone_field or "mobile"
        if not template or not gateway:
            raise UserError(
                self.env._("The WhatsApp template or gateway is not configured.")
            )
        if phone_field not in partner._fields or not partner[phone_field]:
            raise UserError(
                self.env._("The partner has no WhatsApp phone number configured.")
            )
        body = template.with_context(
            default_res_model=self.res_model,
            default_res_id=self.res_id,
        ).render_body_message()
        channel = partner._whatsapp_get_channel(phone_field, gateway)
        if not channel:
            raise UserError(
                self.env._("No WhatsApp gateway channel could be resolved.")
            )
        return channel.with_context(
            whatsapp_template_id=template.id,
            default_res_model=self.res_model,
            default_res_id=self.res_id,
        ).message_post(
            body=body,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
        )

    def _handle_send_error(self, error):
        """Retry later, or give up after ``max_retries`` attempts."""
        self.ensure_one()
        max_retries = self.rule_id.max_retries if self.rule_id else 0
        vals = {"error_message": str(error)}
        if self.retry_count < max_retries:
            vals.update(
                {
                    "state": "pending",
                    "retry_count": self.retry_count + 1,
                    "scheduled_date": fields.Datetime.now() + timedelta(hours=1),
                }
            )
        else:
            vals["state"] = "error"
        self.write(vals)
        return True

    def action_send(self):
        """Send the notifications in this recordset, one savepoint at a time."""
        for notification in self.filtered(
            lambda rec: rec.state in ("draft", "pending", "error")
        ):
            try:
                with self.env.cr.savepoint():
                    message = notification._send_whatsapp()
                    notification.write(
                        {
                            "state": "sent",
                            "sent_date": fields.Datetime.now(),
                            "message_id": message.id if message else False,
                            "error_message": False,
                        }
                    )
            except Exception as error:  # pylint: disable=broad-except
                _logger.warning(
                    "WhatsApp notification %s failed: %s", notification.id, error
                )
                notification._handle_send_error(error)
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_reset(self):
        self.write({"state": "pending", "retry_count": 0, "error_message": False})
        return True

    def action_send_now(self):
        self.write({"scheduled_date": fields.Datetime.now(), "state": "pending"})
        return self.action_send()

    @api.model
    def _cron_process_notifications(self):
        """Auto-schedule configured rules, then send all due notifications."""
        self.env["whatsapp.notification.rule"]._cron_schedule_notifications()
        due = self.search(
            [
                ("state", "=", "pending"),
                ("scheduled_date", "<=", fields.Datetime.now()),
            ],
            limit=200,
        )
        if due:
            due.action_send()
        return True
