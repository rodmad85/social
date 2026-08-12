import logging

from odoo import models

_logger = logging.getLogger(__name__)


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

    def _receive_calls_update(self, gateway, value):
        try:
            from odoo.addons.odoo_whatsapp_calling.controllers.main_meta import (
                WaCallWebhook,
            )

            controller = WaCallWebhook()
            data = {"entry": [{"changes": [{"value": value}]}]}
            controller._process_calls_update(data)
        except ImportError:
            _logger.warning(
                "odoo_whatsapp_calling module not installed, ignoring calls webhook"
            )
        except Exception:
            _logger.exception("Error processing WhatsApp calls webhook")
