from odoo import models


class MailWhatsAppTemplate(models.Model):
    _inherit = "mail.whatsapp.template"

    def prepare_value_to_send(self):
        self.ensure_one()
        model_name = self.model_id.model
        rec_id = self.env.context.get("default_res_id")
        if rec_id is None:
            rec_ids = self.env.context.get("res_id")
            if rec_ids:
                rec_id = rec_ids
            else:
                rec_id = None
        record = self.env[model_name].browse(int(rec_id)) if model_name and rec_id else self.env[model_name]
        components = []
        variable_ids_value = self.variable_ids._get_variables_value(record)
        header = self._prepare_header_component(variable_ids_value=variable_ids_value)
        body = self._prepare_body_components(variable_ids_value=variable_ids_value)
        buttons = self._prepare_button_components(variable_ids_value=variable_ids_value)
        if header:
            components.append(header)
        if body:
            components.append(body)
        components.extend(buttons)
        return components

    def render_body_message(self):
        self.ensure_one()
        model_name = self.model_id.model
        rec_id = self.env.context.get("default_res_id")
        if rec_id is None:
            rec_ids = self.env.context.get("default_res_ids")
            if isinstance(rec_ids, list) and rec_ids:
                rec_id = rec_ids[0]
            else:
                rec_id = None
        record = self.env[model_name].browse(int(rec_id)) if model_name and rec_id else self.env[model_name]
        header = ""
        if self.header:
            header = self.header
            header_vars = self.variable_ids.filtered(lambda v: v.line_type == "header")
            for i, var in enumerate(header_vars, start=1):
                placeholder = f"{{{{{i}}}}}"
                value = var._get_variables_value(record).get(
                    f"header-{placeholder}", ""
                )
                header = header.replace(placeholder, str(value))
        body = self.body or ""
        body_vars = self.variable_ids.filtered(lambda v: v.line_type == "body")
        for i, var in enumerate(body_vars, start=1):
            placeholder = f"{{{{{i}}}}}"
            value = var._get_variables_value(record).get(f"body-{placeholder}", "")
            body = body.replace(placeholder, str(value))
        message = f"*{header}*\n\n{body}" if header else body
        return message
