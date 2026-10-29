# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Id prefix used on the WhatsApp interactive options so that the customer's
# click can be mapped back to the exact ``chatbot.script.answer``.
ANSWER_ID_PREFIX = "wa_ans_"


class MailGatewayWhatsappService(models.AbstractModel):
    _inherit = "mail.gateway.whatsapp"

    # ------------------------------------------------------------------
    # Outgoing interactive messages (buttons / list)
    # ------------------------------------------------------------------
    def _get_whatsapp_interactive_payload(self, record):
        """Send the questions of the WhatsApp bot as interactive messages.

        Any message posted by a chatbot operator that is the
        ``question_selection`` step of a script is sent as WhatsApp reply
        buttons (3 options or less) or as a list (more options), so the
        customer answers with a single tap instead of typing the option.
        """
        message = record.mail_message_id
        step = self._whatsapp_chatbot_step_of_message(message)
        if not step or step.step_type != "question_selection" or not step.answer_ids:
            return False
        return {
            "type": "button" if len(step.answer_ids) <= 3 else "list",
            "body": html2plaintext(message.body or ""),
            "button_label": self.env._("See options"),
            "section_title": self.env._("Options"),
            "options": [
                {"id": f"{ANSWER_ID_PREFIX}{answer.id}", "title": answer.name}
                for answer in step.answer_ids
            ],
        }

    def _whatsapp_chatbot_step_of_message(self, message):
        """Return the chatbot step ``message`` is the bot's post of, if any."""
        if not message or message.model != "discuss.channel":
            return self.env["chatbot.script.step"]
        chatbot_message = (
            self.env["chatbot.message"]
            .sudo()
            .search([("mail_message_id", "=", message.id)], limit=1)
        )
        step = chatbot_message.script_step_id
        if not step or message.author_id != step.chatbot_script_id.operator_partner_id:
            # not a bot message (e.g. the customer's own reply, which is also
            # tracked by ``chatbot.message``)
            return self.env["chatbot.script.step"]
        return step

    # ------------------------------------------------------------------
    # Incoming interactive replies
    # ------------------------------------------------------------------
    def _whatsapp_interactive_reply_text(self, message):
        """Human readable label of a button / list reply."""
        for key in ("button", "list_reply"):
            payload = message.get(key)
            if not isinstance(payload, dict):
                continue
            for field in ("title", "text", "payload"):
                if payload.get(field):
                    return str(payload[field])
        return ""

    def _whatsapp_interactive_reply_ids(self, message):
        """Raw ids sent back by a button / list reply."""
        raw_ids = []
        for key in ("button", "list_reply"):
            payload = message.get(key)
            if not isinstance(payload, dict):
                continue
            for field in ("payload", "id"):
                if payload.get(field):
                    raw_ids.append(str(payload[field]))
        return raw_ids

    @staticmethod
    def _whatsapp_normalize_answer(value):
        return " ".join(str(value or "").replace("\xa0", " ").strip().lower().split())

    def _whatsapp_chatbot_match_answer(self, step, message):
        """Map an interactive WhatsApp reply to a ``chatbot.script.answer``.

        The button id (encoded by us) is authoritative; the visible label and
        the option position ("1", "2"...) are used as fallbacks so replies
        also work when the customer types the answer instead of tapping it.
        """
        answer_model = self.env["chatbot.script.answer"].sudo()
        if not step:
            return answer_model
        for raw_id in self._whatsapp_interactive_reply_ids(message):
            if raw_id.startswith(ANSWER_ID_PREFIX) and raw_id[len(ANSWER_ID_PREFIX):].isdigit():
                answer = answer_model.browse(
                    int(raw_id[len(ANSWER_ID_PREFIX):])
                ).exists()
                if answer in step.answer_ids:
                    return answer
        labels = {}
        for lang in {self.env.lang, "pt_BR", "en_US"} - {False}:
            for answer in step.answer_ids:
                labels.setdefault(answer.id, set()).add(
                    self._whatsapp_normalize_answer(
                        answer.with_context(lang=lang).name
                    )
                )
        label = self._whatsapp_normalize_answer(
            self._whatsapp_interactive_reply_text(message)
        )
        if not label:
            return answer_model
        if label.isdigit() and 1 <= int(label) <= len(step.answer_ids):
            return step.answer_ids[int(label) - 1]
        for answer in step.answer_ids:
            if label in labels.get(answer.id, ()):
                return answer
        return answer_model

    # ------------------------------------------------------------------
    # Inbound flow
    # ------------------------------------------------------------------
    @api.model
    def _whatsapp_livechat_channel(self, gateway):
        return self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", gateway.id)], limit=1
        )

    @api.model
    def _whatsapp_conversation(self, livechat_channel, chat):
        if not livechat_channel:
            return self.env["discuss.channel"]
        return self.env["discuss.channel"].search(
            [
                ("channel_type", "=", "livechat"),
                ("livechat_channel_id", "=", livechat_channel.id),
                ("gateway_channel_token", "=", chat.gateway_channel_token),
            ],
            limit=1,
        )

    def _process_update(self, chat, message, value):
        """Mirror inbound gateway messages into the linked livechat channel.

        The base implementation posts the webhook message on the gateway (bot)
        channel. When the gateway is linked to an ``im_livechat.channel``, the
        message is mirrored into the livechat conversation channel where the
        operator answers, reusing the existing conversation by
        ``gateway_channel_token``.

        On top of that, when the livechat channel has a
        ``whatsapp_chatbot_script_id``, the scripted flow runs:

        - first contact: the welcome steps (first question included) are
          posted and sent to the customer as interactive buttons;
        - further messages: the customer's answer (typed, or tapped on a
          button/list) drives the script forward until it ends or hands over
          to a human.
        """
        livechat_channel = self._whatsapp_livechat_channel(chat.gateway_id)
        conversation = self._whatsapp_conversation(livechat_channel, chat)
        selected_answer = self.env["chatbot.script.answer"].sudo()
        if conversation and conversation.chatbot_current_step_id:
            selected_answer = self._whatsapp_chatbot_match_answer(
                conversation.chatbot_current_step_id, message
            )
        if message.get("button") or message.get("list_reply") or (
            message.get("type") in ("button", "list_reply")
        ):
            # an interactive reply carries no text body: turn it into one so
            # it is recorded on the gateway channel and mirrored as usual
            if selected_answer:
                lang = self.env["discuss.channel"]._whatsapp_chatbot_lang(
                    conversation, False
                )
                reply_label = selected_answer.with_context(lang=lang).name
            else:
                reply_label = self._whatsapp_interactive_reply_text(message)
            if reply_label:
                message = dict(message)
                message["type"] = "text"
                message["text"] = {"body": reply_label}
        previous_message_id = (
            self.env["mail.message"]
            .search(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", chat.id),
                    ("message_type", "=", "comment"),
                ],
                order="id desc",
                limit=1,
            )
            .id
        )
        super()._process_update(chat, message, value)
        if not livechat_channel:
            return
        posted = self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", chat.id),
                ("message_type", "=", "comment"),
            ],
            order="id desc",
            limit=1,
        )
        if not posted or posted.id == previous_message_id:
            # nothing was recorded for this webhook message
            return
        created = False
        if not conversation:
            vals = self.env["discuss.channel"]._get_livechat_whatsapp_channel_vals(
                chat.gateway_id, chat.gateway_channel_token, value
            )
            if not vals:
                return
            conversation = self.env["discuss.channel"].create(vals)
            conversation._broadcast(
                conversation.channel_member_ids.mapped("partner_id").ids
            )
            created = True
        author = self._get_author(chat.gateway_id, value)
        mirror_context = {
            "no_gateway_notification": True,
            "whatsapp_inbound": True,
        }
        if selected_answer:
            mirror_context["selected_answer_id"] = selected_answer.id
        mirror = conversation
        if author and author._name == "mail.guest":
            mirror = mirror.with_user(self.env.ref("base.public_user").id)
            mirror_context["guest"] = author
        mirror.sudo().with_context(**mirror_context).message_post(
            body=posted.body,
            author_id=author and author._name == "res.partner" and author.id,
            date=posted.date,
            subtype_xmlid="mail.mt_comment",
            message_type="comment",
            attachment_ids=posted.attachment_ids.ids,
        )
        if created:
            conversation._whatsapp_chatbot_start(conversation, author)
        elif conversation.chatbot_current_step_id:
            conversation._whatsapp_chatbot_advance(
                posted.body, selected_answer=selected_answer
            )
