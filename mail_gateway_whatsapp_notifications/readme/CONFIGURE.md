# Configuration

1. Install `mail_gateway_whatsapp` and synchronise/approve the Meta WhatsApp
   templates that will be used (menu *WhatsApp*).
2. Open **Discuss → WhatsApp → Regras de Notificação** and create one rule per
   event:
   - **Event Key**: technical key used by the calling addon (for instance
     `clinical_appointment_confirmation`). It must match exactly.
   - **Applies to**: any non-transient Odoo model (Contacts, Sale Orders,
     Clinical sessions, ...).
   - **Template**: an approved `mail.whatsapp.template`. A rule without a
     template is simply ignored, so it can be created before the template is
     approved.
   - **Recipient Field**: name of a `res.partner` Many2one on the source model
     (default `partner_id`).
   - **Phone Field**: field of `res.partner` holding the WhatsApp number
     (default `mobile`).
   - **Date Field** and **Offset**: the send date is computed from that
     Date/Datetime field plus `offset_days` / `offset_hours`. Use a negative
     offset for reminders sent before an appointment.
   - **Auto Schedule** and **Domain**: let the cron scan the model (static
     Python literal domain) and enqueue matching records automatically.
   - **Max Retries**: how many times a failed send is retried (one hour apart).
3. The scheduled action *WhatsApp: Schedule and Send Template Notifications*
   is created active, every 15 minutes. Adjust its interval in
   *Settings → Technical → Automation → Scheduled Actions* if needed.

Only users in `base.group_system` may edit rules; gateway users can consult
the agenda. Internal users may enqueue notifications through the public API.
