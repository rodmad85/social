# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Livechat WhatsApp Integration",
    "summary": "Integrate WhatsApp gateway with livechat channels",
    "version": "18.0.1.1.0",
    "license": "AGPL-3",
    "author": "Madooit, Odoo Community Association (OCA)",
    "maintainers": ["rodmad85"],
    "website": "https://github.com/OCA/social",
    "depends": [
        "mail_gateway_whatsapp",
        "im_livechat",
        "ai_connection",
        "ai_connection_openai",
        "ai_tool",
        "clinical_management",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ai_tools_data.xml",
        "views/im_livechat_channel_views.xml",
        "views/discuss_channel_views.xml",
        "actions/ai_whatsapp_actions.xml",
    ],
    "installable": True,
    "auto_install": False,
}
