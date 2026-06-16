{
    "name": "Mail Gateway Adjustments",
    "summary": "Private WhatsApp conversations, unassigned channels, transfer, and chatter sync",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/social",
    "depends": ["mail", "mail_gateway", "mail_gateway_whatsapp"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/unassigned_channel_views.xml",
        "views/transfer_wizard_views.xml",
    ],
}
