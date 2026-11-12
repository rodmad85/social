# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.addons.mail.tools.discuss import Store
from odoo import models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _to_store(self, store: Store):
        result = super()._to_store(store)
        for record in self:
            store.add(record, {"gateway_channel_token": record.gateway_channel_token})
        return result
