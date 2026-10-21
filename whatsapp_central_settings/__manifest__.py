# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "WhatsApp Central Settings",
    "summary": "Configurações centralizadas do WhatsApp em Definições",
    "description": """Unifica, em um único local no menu Definições, as principais
configurações dos módulos de WhatsApp disponíveis nas pastas ``social`` e
``whatsappcall``:

* Recebimento de ligações: quem deverá receber as ligações.
* Efetuar ligações: quem pode efetuar ligações.
* Editar templates de mensagem: quem pode editar as configurações dos
  templates de mensagem.
* Mensagens não atribuídas: vão para a lista de mensagens ou são atribuídas
  diretamente a um usuário.
* Quem pode ver o menu WhatsApp - Conversas no módulo Mensagens (Discuss).

Os valores são armazenados em parâmetros do sistema (``ir.config_parameter``)
e permanecem acessíveis mesmo quando os módulos de chamada do WhatsApp
(``odoo_whatsapp_calling``) ainda não estão instalados neste ambiente.""",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Madooit,Odoo Community Association (OCA)",
    "maintainers": ["rodmad85"],
    "website": "https://github.com/OCA/social",
    "category": "Messaging",
    "depends": [
        "base",
        "mail_gateway",
        "mail_gateway_whatsapp",
        "mail_gateway_whatsapp_messages",
        "odoo_whatsapp_calling",
        "tus_meta_whatsapp_base",
        "tus_meta_wa_discuss",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_partner_inherit_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "whatsapp_central_settings/static/src/core/web/chatter.xml",
            "whatsapp_central_settings/static/src/core/common/composer.js",
        ],
    },
    "installable": True,
    "application": False,
}
