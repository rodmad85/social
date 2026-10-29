Configuration
=============

1. Go to **Discuss** > **Livechat** > **Channels**.
2. Open or create a livechat channel.
3. In the **WhatsApp** tab, select the WhatsApp gateway to link.
4. (Optional) Assign operators to the livechat channel.
5. (Optional) Select a **WhatsApp Bot Script** (any ``chatbot.script``).

Operators are optional
----------------------

The module does not need anybody connected to work:

- If an operator is **online**, the standard livechat assignment is used
  (availability, language, country).
- Otherwise the conversation falls back to the operators configured on
  the livechat channel, then to the members of the WhatsApp gateway,
  then to any user with the livechat operator group.

A livechat channel always needs an operator partner (Odoo constraint),
so the module never creates a conversation without one.

WhatsApp bot script (first contact)
-----------------------------------

When a **WhatsApp Bot Script** is set on the livechat channel:

- On the **first** message of a customer, the script's welcome steps are
  posted and sent to the customer, ending on the first question.
- Questions of type *Selection* are sent as **WhatsApp interactive
  messages**: up to 3 answers are shown as reply buttons, more than 3 as
  a list. The customer taps an option and the answer drives the script
  forward (typing the option, or its position ``1``, ``2``, ... also
  works).
- The conversation is mirrored to the gateway (bot) channel, so
  attendants follow the whole thread from there and can talk to the
  customer directly.
- The bot **stops** when the script ends, when a *forward to operator*
  step is reached, or as soon as an attendant replies — either on the
  livechat conversation or on the gateway channel.

The bot messages are written in the company language (``pt_BR`` by
default), unless the customer's partner has another language set.

Usage
=====

Once configured:

- Incoming WhatsApp messages from customers will appear as livechat
  sessions in Discuss.
- Operators are automatically assigned based on the livechat channel's
  operator selection logic (availability, language, country).
- Operators can respond directly in Discuss and messages are sent
  back via WhatsApp. They can also answer from the gateway (bot)
  channel itself: those messages are sent to the customer too.
- The full thread is mirrored on the gateway (bot) channel, so gateway
  administrators see the customer conversation even before an operator
  opens it.
- If a **WhatsApp Bot Script** is configured, the scripted questions are
  sent automatically on the first contact (see above) and the attendants
  take over as soon as they reply.
- The livechat session inherits all standard livechat features including
  ratings and chatbot integration.
