{
    "name": "Mail WhatsApp Gateway Messages",
    "summary": "List view of WhatsApp messages grouped by contact and model",
    "version": "18.0.1.0.2",
    "license": "AGPL-3",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/social",
    "depends": ["mail", "mail_gateway", "mail_gateway_whatsapp_chatter", "sales_team"],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_whatsapp_message_views.xml",
        "views/whatsapp_assign_conversation_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_gateway_whatsapp_messages/static/src/scss/mail_whatsapp_kanban.scss",
        ],
    },
}
