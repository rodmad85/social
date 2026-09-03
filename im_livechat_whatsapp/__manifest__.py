# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Livechat WhatsApp Integration",
    "summary": "Integrate WhatsApp gateway with livechat channels",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Madooit, Odoo Community Association (OCA)",
    "maintainers": ["rodmad85"],
    "website": "https://github.com/OCA/social",
    "depends": ["mail_gateway_whatsapp", "im_livechat"],
    "data": [
        "views/im_livechat_channel_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
