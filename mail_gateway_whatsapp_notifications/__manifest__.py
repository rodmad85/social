# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "WhatsApp Template Notification Scheduling",
    "summary": "Schedule and organise WhatsApp template messages for any Odoo model",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Madooit,Odoo Community Association (OCA)",
    "maintainers": ["rodmad85"],
    "website": "https://github.com/OCA/social",
    "category": "Messaging",
    "depends": [
        "mail_gateway_whatsapp",
        "mail_gateway_whatsapp_messages",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/whatsapp_notification_rule_views.xml",
        "views/whatsapp_notification_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
