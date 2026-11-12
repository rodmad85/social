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

    def _get_template_record(self):
        """Return the record used to fill the template variables.

        The chatter sends templates from a ``discuss.channel``, so the
        record id is usually not present in the context. In that case use the
        record linked to the channel (the CRM opportunity, for example).
        """
        self.ensure_one()
        model_name = self.model or "res.partner"
        rec_id = self.env.context.get("default_res_id")
        if rec_id is None:
            rec_id = self.env.context.get("res_id")
        if isinstance(rec_id, (list, tuple)):
            rec_id = rec_id[0] if rec_id else None
        context_model = self.env.context.get("default_res_model")

        def _from_record(record_model, record_id):
            record = self.env[record_model].browse(int(record_id))
            if record_model == model_name:
                return record
            if model_name == "res.partner" and "partner_id" in record._fields:
                return record.partner_id or self.env["res.partner"]
            return None

        # An explicit model/id pair in the context is the most reliable source.
        if rec_id and context_model:
            record = _from_record(context_model, rec_id)
            if record is not None:
                return record

        # In the chatter the business record is linked to the channel and may
        # be different from the template model (e.g. a crm.lead whose partner
        # receives the message).
        channel_id = self.env.context.get("gateway_channel_id")
        if channel_id:
            links = (
                self.env["mail.whatsapp.chatter.link"]
                .sudo()
                .search(
                    [("channel_id", "=", channel_id)],
                    order="create_date desc, id desc",
                )
            )
            for link in links:
                if link.res_model == model_name:
                    return self.env[model_name].browse(link.res_id)
            for link in links:
                if model_name != "res.partner":
                    continue
                if link.partner_id:
                    return link.partner_id
                record = self.env[link.res_model].browse(link.res_id)
                if "partner_id" in record._fields and record.partner_id:
                    return record.partner_id
            return self.env[model_name]

        # Automated actions set res_id but not default_res_model; in that case
        # the template model is the action model.
        if rec_id:
            record = _from_record(context_model or model_name, rec_id)
            if record is not None:
                return record
        return self.env[model_name]

    def prepare_value_to_send(self):
        self.ensure_one()
        record = self._get_template_record()
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
        record = self._get_template_record()
        header = self.header or ""
        for var in self.variable_ids.filtered(lambda v: v.line_type == "header"):
            value = var._get_variables_value(record).get(f"header-{var.name}", "")
            header = header.replace(var.name, str(value))
        body = self.body or ""
        for var in self.variable_ids.filtered(lambda v: v.line_type == "body"):
            value = var._get_variables_value(record).get(f"body-{var.name}", "")
            body = body.replace(var.name, str(value))
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
