{
    "name": "Mail Gateway WhatsApp Call",
    "summary": "Bridge WhatsApp Calling webhook events (calls field) from mail_gateway_whatsapp to odoo_whatsapp_calling",
    "version": "18.0.1.1.0",
    "license": "AGPL-3",
    "author": "IOMR",
    "depends": ["mail_gateway_whatsapp", "odoo_whatsapp_calling"],
    "data": [
        "views/res_partner_inherit_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_gateway_whatsapp_call/static/src/components/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
