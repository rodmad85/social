{
    "name": "WhatsApp Call IOMR Patch",
    "version": "18.0.1.0.3",
    "category": "Hidden",
    "summary": "Local patches for WhatsApp calls and for the Odoo bus worker",
    "description": """
This module contains the IOMR customizations that used to be applied
directly on the vendor module `odoo_whatsapp_calling` and on the Odoo
`bus` addon:

* the "Call on WhatsApp" button starts the business initiated call from
  the tab that clicked it (client action), instead of depending on a
  bus/websocket notification;
* the websocket worker aborts a connection attempt that never completes
  (CONNECTING forever) and retries with a fresh socket.

Everything else stays untouched on the original modules, which makes
future upgrades of the vendor module and of Odoo much easier.
""",
    "author": "IOMR",
    "license": "LGPL-3",
    "depends": [
        "odoo_whatsapp_calling",
        "bus",
        "mail_gateway",
        "tus_meta_wa_discuss",
    ],
    "data": [
        "views/wa_compose_message_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "whatsappcall_iomr_patch/static/src/js/whatsapp_call_action.js",
            # Remove o atalho "Client" do Discuss (abre res.partner errado para guests).
            "whatsappcall_iomr_patch/static/src/js/remove_client_action.js",
        ],
        "bus.websocket_worker_assets": [
            (
                "replace",
                "bus/static/src/workers/websocket_worker.js",
                "whatsappcall_iomr_patch/static/src/bus/websocket_worker.js",
            ),
        ],
    },
    "post_load": "post_load",
    "installable": True,
    "application": False,
}
