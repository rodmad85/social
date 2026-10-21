from odoo import _, api, fields, models, modules, tools
from odoo.addons.mail.tools.discuss import Store


class Thread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _thread_to_store(self, store: Store, /, *, request_list=None, **kwargs):
        super()._thread_to_store(store, request_list=request_list, **kwargs)
        model_id = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1).id
        DisableWpCallBtn = False if model_id in self.env.company.not_wa_call_btn_in_chatter.ids else True
        if request_list:
            store.add(
                self,
                {"DisableWpCallBtn": DisableWpCallBtn},
                as_thread=True,
            )
