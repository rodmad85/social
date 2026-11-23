# Usage

Go to **Discuss → WhatsApp → Notificações** to see the agenda: every queued
message, its scheduled date, recipient, template, source record and state
(`pending`, `sent`, `error`, `cancelled`). From a notification you can
**Send Now**, **Cancel** or **Reset** a failed one. **Regras de Notificação**
opens the configuration, where **Schedule Now** enqueues the records matching
the rule domain immediately.

## For addon developers

Enqueue from any model with the public API:

```python
self.env["whatsapp.notification"].schedule(
    "my_module_my_event",
    records,
    scheduled_date=my_datetime,  # optional; otherwise the rule computes it
)
```

The call is safe to make unconditionally: when no active rule matches the
event key and model, or when the rule has no template yet, nothing is created
and a debug message is logged. A rule is required for each `(event_key,
model, company)`; duplicates for the same source record are ignored while a
`draft`, `pending` or `sent` notification already exists.

Sending uses the standard gateway API
(`res.partner._whatsapp_get_channel()` + `message_post` with
`whatsapp_template_id` in the context), so template variables and the 24h
conversation rules of `mail_gateway_whatsapp` keep applying.
