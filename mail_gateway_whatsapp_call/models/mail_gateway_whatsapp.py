import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def resolve_whatsapp_call_partner_id(self, model_name, res_id):
        record = self.env[model_name].browse(res_id)
        if model_name == "res.partner":
            return record.id or False
        if "partner_id" in record._fields and record.partner_id:
            return record.partner_id.id
        return False


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    def _receive_update(self, gateway, update):
        if update:
            for entry in update["entry"]:
                for change in entry["changes"]:
                    if change["field"] != "calls":
                        continue
                    self._receive_calls_update(gateway, change["value"])
        return super()._receive_update(gateway, update)

    @api.model
    def _whatsapp_get_sender(self, data):
        """Return the sender identifier of a message or call payload."""
        return data.get("from") or data.get("from_user_id") or data.get("user_id")

    @api.model
    def _whatsapp_get_recipient(self, data):
        """Return the recipient identifier of a status payload."""
        return data.get("recipient_id") or data.get("recipient_user_id")

    def _receive_calls_update(self, gateway, value):
        try:
            from odoo.http import request

            from odoo.addons.odoo_whatsapp_calling.controllers.main_meta import (
                WaCallWebhook,
            )

            controller = WaCallWebhook()
            data = {"entry": [{"changes": [{"value": value}]}]}
            request.update_context(whatsapp_call_restrict_channel=True)
            controller._process_calls_update(data)
        except ImportError:
            _logger.warning(
                "odoo_whatsapp_calling module not installed, ignoring calls webhook"
            )
        except Exception:
            _logger.exception("Error processing WhatsApp calls webhook")

    def _receive_update(self, gateway, update):
        # First, route call_permission_reply from messages field to the call controller
        if update:
            for entry in update["entry"]:
                for change in entry["changes"]:
                    if change["field"] != "messages":
                        continue
                    for message in change["value"].get("messages", []):
                        interactive = message.get("interactive") or {}
                        if interactive.get("type") == "call_permission_reply":
                            try:
                                from odoo.http import request
                                from odoo.addons.odoo_whatsapp_calling.controllers.main_meta import (
                                    WaCallWebhook,
                                )

                                controller = WaCallWebhook()
                                full_data = {
                                    "entry": [
                                        {
                                            "changes": [
                                                {"value": change["value"]}
                                            ]
                                        }
                                    ]
                                }
                                if request:
                                    request.update_context(
                                        whatsapp_call_restrict_channel=True
                                    )
                                controller._process_calls_update(full_data)
                            except ImportError:
                                _logger.warning(
                                    "odoo_whatsapp_calling not installed, "
                                    "ignoring call_permission_reply"
                                )
                            except Exception:
                                _logger.exception(
                                    "Error processing call_permission_reply"
                                )
        return super()._receive_update(gateway, update)


class Provider(models.Model):
    _inherit = "provider"

    def get_channel_whatsapp(self, partner, user):
        channel = super().get_channel_whatsapp(partner, user)
        if (
            channel
            and self._context.get("whatsapp_call_restrict_channel")
            and self.wa_call_responsible_user_ids
        ):
            allowed_partner_ids = {partner.id if partner else False}
            allowed_partner_ids.update(
                resp_user.partner_id.id
                for resp_user in self.wa_call_responsible_user_ids
            )
            if user:
                allowed_partner_ids.add(user.partner_id.id)
            if self.user_id:
                allowed_partner_ids.add(self.user_id.partner_id.id)
            to_remove = channel.channel_partner_ids.filtered(
                lambda cp: cp.id not in allowed_partner_ids
            )
            if to_remove:
                channel.sudo().write(
                    {"channel_partner_ids": [(3, cp.id) for cp in to_remove]}
                )
        return channel
