# WhatsApp Call IOMR Patch

Patch module with the IOMR customizations that used to be applied directly
on the vendor module `odoo_whatsapp_calling` and on the Odoo `bus` addon.

Keeping them here means the vendor module and Odoo itself can be updated
without losing the fixes (or having to re-apply them by hand).

## What it does

### 1. "Call on WhatsApp" button without the bus

The vendor implementation of `res.partner.initiate_call_on_whatsapp` (and
`wa.compose.message.call_on_whatsapp`) publishes a `whatsapp_call_service`
bus notification and relies on the browser websocket to receive it. When the
browser is not connected to the bus (network/VPN change, stale worker, ...),
the button appears to do nothing.

This module overrides both methods and returns an `ir.actions.client` action
(`whatsapp_calling.initiate_business_call`) instead. The tab that received
the click builds the WebRTC offer and calls `/wa/call/initiate` itself, with
no websocket involved.

The multi-provider selection wizard is kept (`super()` is called for it).

### 2. Websocket worker handshake timeout

`addons/bus/static/src/workers/websocket_worker.js` is replaced (asset
directive `replace`) by `static/src/bus/websocket_worker.js`, which adds
`CONNECT_TIMEOUT_DELAY` (10s): a socket stuck in `CONNECTING` is aborted and
the worker retries with a fresh socket. Without it, `_start()` returns early
forever because `_isWebsocketConnecting()` stays true.

The worker is served from `/bus/websocket_worker_bundle?v=<version>`, so the
version must change when the file changes. `post_load()` in `__init__.py`
sets `WebsocketConnectionHandler._VERSION` to `18.0-8-iomr.1`.

## Important when upgrading Odoo

`static/src/bus/websocket_worker.js` is a **copy** of the upstream file with
the timeout added. When `addons/bus/static/src/workers/websocket_worker.js`
changes (Odoo upgrade), port the new file here again and bump
`BUS_WORKER_VERSION` in `__init__.py`.

## Related changes kept in `extra/social`

Two small changes are still needed in the modules that trigger the call from
the chatter, so that they execute any action returned by the server (not
only `ir.actions.act_window`):

* `mail_gateway_whatsapp_chatter/static/src/js/whatsapp_call_thread_action.esm.js`
* `mail_gateway_whatsapp_call/static/src/components/send_whatsapp_call_button/send_whatsapp_call_button.esm.js`
