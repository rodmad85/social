from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MailWhatsAppTemplate(models.Model):
    _inherit = "mail.whatsapp.template"

    model_id = fields.Many2one(
        string="Applies to",
        comodel_name="ir.model",
        default=lambda self: self.env["ir.model"].sudo()._get_id("res.partner"),
        required=True,
        ondelete="cascade",
    )

    def prepare_value_to_send(self):
        self.ensure_one()
        model_name = self.model
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
        model_name = self.model
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


class MailWhatsAppTemplateVariable(models.Model):
    _inherit = "mail.whatsapp.template.variable"

    @api.constrains("field_name")
    def _check_field_name(self):
        failing = self.browse()
        missing = self.filtered(lambda variable: not variable.field_name)
        if missing:
            raise ValidationError(
                self.env._(
                    "Field template variables %(variables)s "
                    "must be associated with a field.",
                    variables=", ".join(missing.mapped("name")),
                )
            )
        for variable in self:
            model = self.env[variable.model]
            if not model.has_access("read"):
                model_description = (
                    self.env["ir.model"].sudo()._get(variable.model).display_name
                )
                raise ValidationError(
                    self.env._(
                        "You can not select field of %(model)s.",
                        model=model_description,
                    )
                )
            try:
                variable._extract_value_from_field_path(model)
            except UserError:
                failing += variable
        if failing:
            model_description = (
                self.env["ir.model"].sudo()._get(failing.mapped("model")[0]).display_name
            )
            raise ValidationError(
                self.env._(
                    "Variables %(field_names)s do not seem to be valid field path "
                    "for model %(model_name)s.",
                    field_names=", ".join(failing.mapped("field_name")),
                    model_name=model_description,
                )
            )
