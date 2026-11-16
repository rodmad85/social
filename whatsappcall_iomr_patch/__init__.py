from odoo.addons.bus.websocket import WebsocketConnectionHandler

from . import models
from . import wizard

# The websocket worker bundle is served from
# `/bus/websocket_worker_bundle?v=<version>`. The version is part of the URL
# so that browsers fetch the new worker as soon as the file changes.
# `websocket_worker.js` is replaced by this module (see the manifest), so the
# version must be bumped here instead of on `addons/bus/websocket.py`.
BUS_WORKER_VERSION = "18.0-8-iomr.1"


def post_load():
    """Force the browser to download the patched websocket worker."""
    WebsocketConnectionHandler._VERSION = BUS_WORKER_VERSION
