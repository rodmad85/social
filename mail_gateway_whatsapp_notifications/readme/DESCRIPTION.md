This module organises the **scheduling of WhatsApp template messages** for
any Odoo model. It adds a configurable rule engine and a send queue (agenda),
processed by a scheduled action, on top of `mail_gateway_whatsapp`.

It is deliberately model-agnostic: a rule binds an approved
`mail.whatsapp.template` to *any* `ir.model`, chooses the recipient field, the
phone field, the date field to compute the send date and the offset to apply.
Other addons only need to call `whatsapp.notification.schedule(event_key,
records)` with a technical event key — no WhatsApp code has to be duplicated.
