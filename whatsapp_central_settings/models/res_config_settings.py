# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import Command, api, fields, models, _

_logger = logging.getLogger(__name__)

PARAM_PREFIX = "whatsapp_central_settings."

MODULE_CALLING = "odoo_whatsapp_calling"
MENU_CALLING_CONVERSATIONS = (
    "mail_gateway_whatsapp_messages.menu_mail_whatsapp_conversations"
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # 1. Recebimento de ligações — quem deverá receber.
    # Mapeia para provider.wa_call_responsible_user_ids quando o módulo de
    # chamada estiver instalado.
    wa_call_receive_user_ids = fields.Many2many(
        "res.users",
        relation="res_config_settings_wa_call_receive_user_rel",
        column1="config_id",
        column2="user_id",
        string="Recebimento de ligações — quem deverá receber",
        help="Usuários responsáveis por receber ligações do WhatsApp. "
        "Sincronizado com provider.wa_call_responsible_user_ids quando o módulo "
        "odoo_whatsapp_calling estiver instalado.",
    )

    # 2. Efetuar ligações — quem pode efetuar.
    wa_call_make_user_ids = fields.Many2many(
        "res.users",
        relation="res_config_settings_wa_call_make_user_rel",
        column1="config_id",
        column2="user_id",
        string="Efetuar ligações — quem pode efetuar",
        help="Usuários autorizados a efetuar ligações via WhatsApp.",
    )

    # 3. Editar configurações de mensagens template — quem pode editar.
    wa_template_edit_user_ids = fields.Many2many(
        "res.users",
        relation="res_config_settings_wa_template_edit_user_rel",
        column1="config_id",
        column2="user_id",
        string="Editar templates de mensagem — quem pode editar",
        help="Usuários autorizados a criar/editar mensagens template do WhatsApp.",
    )

    # 4. Mensagens não atribuídas.
    wa_unassigned_action = fields.Selection(
        [
            ("list", "Ir para a lista de mensagens"),
            ("assign", "Atribuir diretamente a um usuário"),
        ],
        string="Mensagens não atribuídas",
        default="list",
        help="Define se as mensagens WhatsApp não atribuídas vão para a lista de "
        "mensagens ou são atribuídas diretamente a um usuário.",
    )
    wa_unassigned_user_id = fields.Many2one(
        "res.users",
        string="Usuário padrão para atribuição",
        help="Usuário ao qual as mensagens não atribuídas serão atribuídas "
        "diretamente, quando a opção acima for 'Atribuir diretamente a um "
        "usuário'.",
    )

    # 5. Quem pode ver o menu WhatsApp - Conversas no módulo Mensagens (Discuss).
    wa_conversation_menu_group_ids = fields.Many2many(
        "res.groups",
        string="Quem pode ver o menu WhatsApp - Conversas",
        help="Grupos de usuários autorizados a ver o menu WhatsApp - Conversas "
        "no módulo Mensagens (Discuss).",
    )

    # -------------------------------------------------------------------------
    # get_values / set_values
    # -------------------------------------------------------------------------

    @api.model
    def get_values(self):
        res = super().get_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()

        def _ids(param_name):
            # x2many fields must be returned as a list of commands (not as a
            # plain list of ids). ``res.config.settings.default_get`` feeds
            # these values into the ``onchange`` machinery, which serializes
            # x2many values as commands; returning bare ints raises
            # "TypeError: 'int' object is not subscriptable".
            raw = ICPSudo.get_param(PARAM_PREFIX + param_name) or ""
            ids = [int(x) for x in raw.split(",") if x.strip()]
            return [Command.set(ids)] if ids else False

        res.update(
            wa_call_receive_user_ids=_ids("wa_call_receive_user_ids"),
            wa_call_make_user_ids=_ids("wa_call_make_user_ids"),
            wa_template_edit_user_ids=_ids("wa_template_edit_user_ids"),
            wa_unassigned_action=(
                ICPSudo.get_param(PARAM_PREFIX + "wa_unassigned_action") or "list"
            ),
            wa_unassigned_user_id=(
                int(ICPSudo.get_param(PARAM_PREFIX + "wa_unassigned_user_id"))
                if ICPSudo.get_param(PARAM_PREFIX + "wa_unassigned_user_id")
                else False
            ),
            wa_conversation_menu_group_ids=_ids("wa_conversation_menu_group_ids"),
        )
        return res

    def set_values(self):
        super().set_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()

        def _store(field_name):
            ids = [str(rec.id) for rec in self[field_name]]
            ICPSudo.set_param(PARAM_PREFIX + field_name, ",".join(ids) if ids else "")

        _store("wa_call_receive_user_ids")
        _store("wa_call_make_user_ids")
        _store("wa_template_edit_user_ids")
        _store("wa_conversation_menu_group_ids")

        ICPSudo.set_param(
            PARAM_PREFIX + "wa_unassigned_action",
            self.wa_unassigned_action or "list",
        )
        ICPSudo.set_param(
            PARAM_PREFIX + "wa_unassigned_user_id",
            str(self.wa_unassigned_user_id.id) if self.wa_unassigned_user_id else "",
        )

        # Sincroniza os responsáveis por receber ligações com o provider, se o
        # módulo de chamada estiver instalado. Não é obrigatório para este
        # módulo; se o modelo 'provider' não existir, apenas mantém o valor no
        # parâmetro do sistema.
        if self.wa_call_receive_user_ids and self._module_installed(MODULE_CALLING):
            try:
                Provider = self.env["provider"].sudo()
                providers = Provider.search([])
                for provider in providers:
                    provider.write(
                        {
                            "wa_call_responsible_user_ids": [
                                (6, 0, self.wa_call_receive_user_ids.ids)
                            ]
                        }
                    )
            except Exception:  # modelo provider não existe neste ambiente
                _logger.warning(
                    "Modelo 'provider' indisponível: o módulo %s não está "
                    "instalado. A configuração de recebimento de ligações foi "
                    "salva apenas no parâmetro do sistema.",
                    MODULE_CALLING,
                )

        # Aplica a visibilidade do menu WhatsApp - Conversas quando houver
        # grupos selecionados.
        menu = self.env.ref(MENU_CALLING_CONVERSATIONS, raise_if_not_found=False)
        if menu and self.wa_conversation_menu_group_ids:
            menu.sudo().write(
                {"groups_id": [(6, 0, self.wa_conversation_menu_group_ids.ids)]}
            )

    def _module_installed(self, module_name):
        return bool(
            self.env["ir.module.module"]
            .search([("name", "=", module_name), ("state", "=", "installed")], limit=1)
        )
