# Copyright 2024 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["mail.thread.phone", "res.partner"]

    wa_user_id = fields.Char(
        string="WhatsApp BSUID",
        index=True,
        copy=False,
        help="Business-scoped user ID (BSUID) sent by Meta when a WhatsApp "
        "user adopts a username and the phone number is not available.",
    )

    def _whatsapp_get_partner(self):
        return self

    def _phone_get_number_fields(self):
        """This method returns the fields to use to find the number to use to
        send an SMS on a record."""
        result = set(super()._phone_get_number_fields())
        result.add("mobile")
        result.add("phone")
        return list(result)
