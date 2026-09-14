# Copyright 2026 Madooit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Mail Gateway WhatsApp Purchase",
    "summary": "Send purchase orders and RFQs by WhatsApp",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Madooit, Odoo Community Association (OCA)",
    "maintainers": ["rodmad85"],
    "website": "https://github.com/OCA/social",
    "depends": ["mail_gateway_whatsapp", "purchase"],
    "data": ["views/purchase_order_views.xml"],
    "installable": True,
    "application": False,
}
