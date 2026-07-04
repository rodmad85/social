{
    "name": "Mail WhatsApp Gateway Chatter",
    "summary": "Bidirectional message sync between chatter and WhatsApp",
    "version": "18.0.1.0.1",
    "license": "AGPL-3",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/social",
    "depends": ["mail", "mail_gateway", "mail_gateway_whatsapp", "sales_team", "crm_commissions"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",

        "views/mail_whatsapp_chatter_views.xml",
        "views/whatsapp_composer_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_gateway_whatsapp_chatter/static/src/js/whatsapp_message_patch.esm.js",
            "mail_gateway_whatsapp_chatter/static/src/js/gateway_follower_patch.esm.js",
            "mail_gateway_whatsapp_chatter/static/src/js/composer_gateway_patch.esm.js",
            "mail_gateway_whatsapp_chatter/static/src/js/whatsapp_delivery_patch.esm.js",
            "mail_gateway_whatsapp_chatter/static/src/js/chatter_composer_patch.esm.js",
            "mail_gateway_whatsapp_chatter/static/src/scss/mail_whatsapp_chatter.scss",
            "mail_gateway_whatsapp_chatter/static/src/xml/chatter_whatsapp_button.xml",
            "mail_gateway_whatsapp_chatter/static/src/xml/whatsapp_gateway_follower.xml",
            "mail_gateway_whatsapp_chatter/static/src/xml/whatsapp_delivery_indicator.xml",
            "mail_gateway_whatsapp_chatter/static/src/xml/whatsapp_gateway_button_patch.xml",
        ],
    },
}
