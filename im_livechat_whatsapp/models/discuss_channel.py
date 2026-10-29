# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging

from odoo import Command, api, fields, models, _
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

ANSWER_ID_PREFIX = "wa_ans_"


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    ai_active = fields.Boolean(string="IA Ativa")
    ai_handed_off = fields.Boolean(string="IA Transferida para humano")
    ai_notice_sent = fields.Boolean(string="Aviso IA enviado")

    def _get_whatsapp_livechat_channel(self, gateway):
        return self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", gateway.id)], limit=1
        )

    def _get_whatsapp_gateway_channel(self):
        if not self.gateway_channel_token or not self.livechat_channel_id:
            return self.env["discuss.channel"]
        gateway = self.livechat_channel_id.whatsapp_gateway_id
        if not gateway:
            return self.env["discuss.channel"]
        return self.search(
            [
                ("channel_type", "=", "gateway"),
                ("gateway_id", "=", gateway.id),
                ("gateway_channel_token", "=", self.gateway_channel_token),
            ],
            limit=1,
        )

    @api.model
    def _pick_least_loaded_user(self, users):
        if not users:
            return users
        read_group = self.env["discuss.channel"]._read_group(
            [
                ("channel_type", "=", "livechat"),
                ("livechat_active", "=", True),
                ("livechat_operator_id", "in", users.partner_id.ids),
            ],
            groupby=["livechat_operator_id"],
            aggregates=["__count"],
        )
        counts = {}
        for partner, count in read_group:
            key = partner.id if hasattr(partner, "id") else partner
            counts[key] = count
        return users.sorted(lambda user: (counts.get(user.partner_id.id, 0), user.id))[0]

    @api.model
    def _get_whatsapp_livechat_operator(self, livechat_channel, gateway):
        user_operator = livechat_channel._get_operator()
        if user_operator:
            return (
                user_operator.partner_id,
                user_operator.livechat_username or user_operator.name,
            )
        candidates = livechat_channel.user_ids.filtered("active")
        if not candidates:
            candidates = gateway.member_ids.filtered("active")
        if not candidates:
            operator_group = self.env.ref(
                "im_livechat.im_livechat_group_user", raise_if_not_found=False
            )
            if operator_group:
                candidates = self.env["res.users"].search(
                    [
                        ("active", "=", True),
                        ("share", "=", False),
                        ("groups_id", "in", operator_group.id),
                    ],
                    limit=1,
                )
        if candidates:
            user = self._pick_least_loaded_user(candidates)
            _logger.info(
                "No online operator for gateway %s: falling back to %s",
                gateway.id,
                user.login,
            )
            return user.partner_id, user.livechat_username or user.name
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        partner = (
            admin.partner_id
            or gateway.company_id.partner_id
            or self.env.company.partner_id
        )
        _logger.warning(
            "No operator configured for gateway %s: using partner %s",
            gateway.id,
            partner.id,
        )
        return partner, partner.name

    @api.model
    def _get_livechat_whatsapp_channel_vals(self, gateway, token, update):
        livechat_channel = self._get_whatsapp_livechat_channel(gateway)
        if not livechat_channel:
            return {}
        operator_partner, operator_name = self._get_whatsapp_livechat_operator(
            livechat_channel, gateway
        )
        if not operator_partner:
            _logger.warning(
                "No operator could be resolved for gateway %s: "
                "conversation not created",
                gateway.id,
            )
            return {}
        author = self.env["mail.gateway.whatsapp"]._get_author(gateway, update)
        name = token
        for contact in update.get("contacts", []):
            if contact.get("wa_id") == token:
                name = contact.get("profile", {}).get("name", token)
                break
        member_partner_ids = set(gateway.member_ids.partner_id.ids)
        member_partner_ids.add(operator_partner.id)
        member_cmds = [
            Command.create({"partner_id": partner_id, "unpin_dt": False})
            for partner_id in member_partner_ids
        ]
        if author:
            if author._name == "res.partner":
                if author.id not in member_partner_ids:
                    member_cmds.append(Command.create({"partner_id": author.id}))
            elif author._name == "mail.guest":
                member_cmds.append(Command.create({"guest_id": author.id}))
        channel_name = " ".join(filter(None, [name, operator_name]))
        return {
            "name": channel_name,
            "channel_type": "livechat",
            "livechat_active": True,
            "livechat_channel_id": livechat_channel.id,
            "livechat_operator_id": operator_partner.id,
            "gateway_channel_token": token,
            "anonymous_name": name,
            "channel_member_ids": member_cmds,
            "company_id": gateway.company_id.id or False,
        }

    @api.model
    def _whatsapp_chatbot_lang(self, conversation, author=False):
        if (
            author
            and author._name == "res.partner"
            and author.lang
            and author.lang != "en_US"
        ):
            return author.lang
        company = conversation.company_id or self.env.company
        return company.partner_id.lang or self.env.lang or "en_US"

    @api.model
    def _whatsapp_chatbot_context(self, conversation, author=False):
        return {
            "lang": self._whatsapp_chatbot_lang(conversation, author),
            "no_gateway_notification": False,
            "whatsapp_chatbot": True,
        }

    @api.model
    def _whatsapp_chatbot_start(self, conversation, author=False):
        script = conversation.livechat_channel_id.whatsapp_chatbot_script_id
        if not script:
            return
        context = self._whatsapp_chatbot_context(conversation, author)
        channel = conversation.with_context(**context)
        try:
            script.with_context(**context)._post_welcome_steps(channel)
            step = channel.chatbot_current_step_id
            if step and step.step_type == "forward_operator":
                self._whatsapp_chatbot_run(channel, step, "")
        except Exception:
            _logger.exception(
                "WhatsApp bot welcome steps failed on channel %s", conversation.id
            )

    @api.model
    def _whatsapp_chatbot_run(self, channel, step, message_body):
        remaining = 50
        while step and remaining > 0:
            remaining -= 1
            if step.step_type == "forward_operator":
                try:
                    step._process_step(channel)
                except Exception:
                    _logger.exception(
                        "WhatsApp bot handoff failed on channel %s", channel.id
                    )
                channel._whatsapp_chatbot_stop("operator handoff")
                return
            try:
                step._process_step(channel)
            except Exception:
                _logger.exception(
                    "WhatsApp bot step %s failed on channel %s", step.id, channel.id
                )
                return
            if step.step_type != "text":
                return
            try:
                step = step._process_answer(channel, message_body)
            except Exception:
                _logger.exception(
                    "WhatsApp bot could not continue on channel %s", channel.id
                )
                return
        if not step:
            channel._whatsapp_chatbot_stop("script finished")

    def _whatsapp_chatbot_advance(self, message_body, selected_answer=False):
        self.ensure_one()
        if not self.chatbot_current_step_id:
            return
        channel = self.with_context(**self._whatsapp_chatbot_context(self))
        step = channel.chatbot_current_step_id
        if step.step_type == "question_selection" and not selected_answer:
            self._whatsapp_chatbot_reask(channel, step)
            return
        try:
            next_step = step._process_answer(channel, message_body)
        except Exception:
            _logger.exception(
                "WhatsApp bot could not process the answer on channel %s", self.id
            )
            self._whatsapp_chatbot_reask(channel, step)
            return
        self._whatsapp_chatbot_run(channel, next_step, message_body)

    def _whatsapp_chatbot_reask(self, channel, step):
        try:
            step._process_step(channel)
        except Exception:
            _logger.exception(
                "WhatsApp bot could not post step %s on channel %s", step.id, channel.id
            )

    def _whatsapp_chatbot_stop(self, reason):
        for channel in self:
            if channel.chatbot_current_step_id:
                channel.sudo().chatbot_current_step_id = False
                _logger.info(
                    "WhatsApp bot stopped on channel %s (%s)", channel.id, reason
                )

    def _whatsapp_paired_conversation(self):
        if not self:
            return self.browse()
        if self.channel_type == "livechat":
            return self
        if not self.gateway_id or not self.gateway_channel_token:
            return self.browse()
        return self.search(
            [
                ("channel_type", "=", "livechat"),
                ("gateway_channel_token", "=", self.gateway_channel_token),
                ("livechat_channel_id.whatsapp_gateway_id", "=", self.gateway_id.id),
            ],
            limit=1,
        )

    def _whatsapp_chatbot_check_takeover(self, message):
        if not message or message.message_type == "notification":
            return
        if (
            self.channel_type == "livechat"
            and self.chatbot_current_step_id
            and not self.env.context.get("whatsapp_chatbot")
            and not self.env.context.get("whatsapp_inbound")
        ):
            self._whatsapp_chatbot_stop("attendant replied on the conversation")
            return
        if (
            self.channel_type == "gateway"
            and self.gateway_id
            and not self.env.context.get("no_gateway_notification")
        ):
            conversation = self._whatsapp_paired_conversation()
            if conversation:
                conversation._whatsapp_chatbot_stop(
                    "attendant replied on the gateway channel"
                )
        if (
            self.channel_type == "livechat"
            and self.ai_active
            and not self.ai_handed_off
            and not self.env.context.get("whatsapp_chatbot")
            and not self.env.context.get("whatsapp_inbound")
        ):
            self.write({"ai_active": False, "ai_handed_off": True})
            _logger.info("WhatsApp AI handoff to human on channel %s (attendant replied)", self.id)
        elif (
            self.channel_type == "gateway"
            and self.gateway_id
            and not self.env.context.get("no_gateway_notification")
        ):
            conversation = self._whatsapp_paired_conversation()
            if conversation and conversation.ai_active and not conversation.ai_handed_off:
                conversation.write({"ai_active": False, "ai_handed_off": True})
                _logger.info("WhatsApp AI handoff to human on channel %s via gateway (attendant replied)", conversation.id)

    def _ai_whatsapp_format_float_time(self, value):
        if value is False or value is None:
            return ""
        try:
            value = float(value)
        except Exception:
            return ""
        hour = int(value)
        minute = int(round((value - hour) * 60))
        return "%02d:%02d" % (hour, minute)

    def _ai_whatsapp_build_system_prompt(self, lc):
        prompt = lc.ai_system_prompt or ""
        replacements = {
            "{OPEN}": self._ai_whatsapp_format_float_time(lc.ai_open_hour),
            "{CLOSE}": self._ai_whatsapp_format_float_time(lc.ai_close_hour),
            "{LUNCH_START}": self._ai_whatsapp_format_float_time(lc.ai_lunch_start_hour),
            "{LUNCH_END}": self._ai_whatsapp_format_float_time(lc.ai_lunch_end_hour),
            "{CAPABILITIES}": lc.ai_capabilities_text or "",
            "{FAQ}": lc.ai_faq_list or "",
            "{open}": self._ai_whatsapp_format_float_time(lc.ai_open_hour),
            "{close}": self._ai_whatsapp_format_float_time(lc.ai_close_hour),
            "{lunch_start}": self._ai_whatsapp_format_float_time(lc.ai_lunch_start_hour),
            "{lunch_end}": self._ai_whatsapp_format_float_time(lc.ai_lunch_end_hour),
            "{capabilities}": lc.ai_capabilities_text or "",
        }
        for k, v in replacements.items():
            prompt = prompt.replace(k, v)
        return prompt

    def _ai_whatsapp_activate(self):
        self.ensure_one()
        lc = self.livechat_channel_id
        if not lc or not lc.ai_enabled:
            return
        if self.ai_notice_sent:
            self.ai_active = True
            return
        notice = lc.ai_notice_message or ""
        replacements = {
            "{open}": self._ai_whatsapp_format_float_time(lc.ai_open_hour),
            "{close}": self._ai_whatsapp_format_float_time(lc.ai_close_hour),
            "{lunch_start}": self._ai_whatsapp_format_float_time(lc.ai_lunch_start_hour),
            "{lunch_end}": self._ai_whatsapp_format_float_time(lc.ai_lunch_end_hour),
            "{capabilities}": lc.ai_capabilities_text or "",
        }
        for k, v in replacements.items():
            notice = notice.replace(k, v)
        if notice:
            try:
                self.sudo().with_context(no_gateway_notification=False).message_post(
                    body=notice,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:
                _logger.exception("Failed to post AI notice on channel %s", self.id)
        self.write({"ai_active": True, "ai_notice_sent": True})

    def _ai_whatsapp_detect_handoff(self, text):
        if not text:
            return False
        text_lower = html2plaintext(str(text)).lower()
        self.ensure_one()
        lc = self.livechat_channel_id
        keywords = []
        if lc and lc.ai_handoff_keywords:
            keywords = [k.strip().lower() for k in lc.ai_handoff_keywords.split(",") if k.strip()]
        for k in keywords:
            if k and k in text_lower:
                return True
        bad_patterns = [
            "criar orçamento",
            "gerar orçamento",
            "marcar consulta",
            "agendar",
            "agendamento",
            "cancelar consulta",
            "remarcar",
            "pedido",
            "venda",
            "nota fiscal",
            "boleto",
            "cpf",
            "cartão",
        ]
        for p in bad_patterns:
            if p in text_lower:
                return True
        return False

    def _ai_whatsapp_handoff(self, reason=""):
        self.ensure_one()
        lc = self.livechat_channel_id
        self.write({"ai_active": False, "ai_handed_off": True})
        msg = lc.ai_transfer_message if lc and lc.ai_transfer_message else "Estou transferindo você para um atendente humano. Aguarde um momento."
        try:
            self.sudo().with_context(no_gateway_notification=False).message_post(
                body=msg,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        except Exception:
            _logger.exception("Failed to post AI handoff message on channel %s", self.id)
        _logger.info("WhatsApp AI handoff on channel %s: %s", self.id, reason)

    def action_ai_whatsapp_takeover(self):
        self.ensure_one()
        user = self.env.user
        partner = user.partner_id
        if partner not in self.channel_member_ids.partner_id:
            self.write({"channel_member_ids": [(4, partner.id)]})
        if not self.livechat_operator_id:
            self.write({"livechat_operator_id": partner.id})
        self.write({"ai_active": False, "ai_handed_off": True})
        try:
            self.sudo().message_post(
                body="Conversa assumida por %s" % user.name,
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
            )
        except Exception:
            pass
        return True

    def _ai_whatsapp_respond(self, user_msg, author=False):
        self.ensure_one()
        lc = self.livechat_channel_id
        if not lc or not lc.ai_enabled or not lc.ai_connection_id:
            return
        if self.ai_handed_off:
            return
        if self._ai_whatsapp_detect_handoff(user_msg):
            self._ai_whatsapp_handoff("keyword or out of scope")
            return
        try:
            history_limit = lc.ai_history_limit or 10
            messages = []
            system_prompt = self._ai_whatsapp_build_system_prompt(lc)
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            domain = [("model", "=", "discuss.channel"), ("res_id", "=", self.id), ("message_type", "=", "comment")]
            msgs = self.env["mail.message"].search(domain, order="id desc", limit=history_limit * 2)
            for m in reversed(msgs):
                body = html2plaintext(m.body or "")
                if not body.strip():
                    continue
                if m.author_id and m.author_id == lc.ai_connection_id.env.ref("base.partner_root"):
                    continue
                role = "assistant" if m.author_id and m.author_id.user_ids and m.author_id.user_ids[:1].has_group("im_livechat.im_livechat_group_user") else "user"
                if m.author_id and m.author_id == self.env.user.partner_id and self.env.context.get("ai_assistant"):
                    role = "assistant"
                messages.append({"role": role, "content": body})
            messages.append({"role": "user", "content": html2plaintext(str(user_msg or ""))})
            tools = lc.ai_tool_ids
            client = lc.ai_connection_id._get_client_openai(tools)
            response = client.handle_message(messages=messages)
            tool_calls = response.get("tool_calls") or []
            if tool_calls and tools:
                tool_results = []
                for tc in tool_calls:
                    tool_name = tc.get("name")
                    args = tc.get("arguments") or {}
                    tool_rec = tools.filtered(lambda t: t.name == tool_name)
                    if not tool_rec:
                        continue
                    try:
                        res = self.env["discuss.channel"].with_context(ai_assistant=True).ai_whatsapp_execute_tool(tool_rec, args)
                        tool_results.append({"tool": tool_name, "result": res})
                    except Exception as e:
                        _logger.exception("AI tool execution failed %s", tool_name)
                        tool_results.append({"tool": tool_name, "error": str(e)})
                if tool_results:
                    messages.append({"role": "assistant", "content": json.dumps({"tool_calls": tool_calls}, ensure_ascii=False)})
                    messages.append({"role": "user", "content": "Resultados das ferramentas:\n" + json.dumps(tool_results, ensure_ascii=False)})
                    response = client.handle_message(messages=messages)
            msg_content = response.get("message", {}).get("content") or ""
            if not msg_content:
                msg_content = "Não consegui responder no momento. Vou transferir você para um atendente humano."
            if self._ai_whatsapp_detect_handoff(msg_content):
                self._ai_whatsapp_handoff("ai response indicates handoff")
                return
            self.sudo().with_context(no_gateway_notification=False).message_post(
                body=msg_content,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        except Exception as e:
            _logger.exception("AI response failed on channel %s", self.id)
            self._ai_whatsapp_handoff("exception")

    def ai_whatsapp_execute_tool(self, tool_rec, args):
        self.ensure_one()
        if tool_rec.function_name == "ai_whatsapp_tool_get_availability":
            return self.ai_whatsapp_tool_get_availability(**args)
        if tool_rec.function_name == "ai_whatsapp_tool_get_prices":
            return self.ai_whatsapp_tool_get_prices(**args)
        return {}

    def _get_whatsapp_livechat_channel(self, gateway):
        """Return the ``im_livechat.channel`` linked to ``gateway`` if any."""
        return self.env["im_livechat.channel"].search(
            [("whatsapp_gateway_id", "=", gateway.id)], limit=1
        )

    def _get_whatsapp_gateway_channel(self):
        """Return the gateway (bot) channel paired to this conversation
        channel for the same WhatsApp phone number."""
        if not self.gateway_channel_token or not self.livechat_channel_id:
            return self.env["discuss.channel"]
        gateway = self.livechat_channel_id.whatsapp_gateway_id
        if not gateway:
            return self.env["discuss.channel"]
        return self.search(
            [
                ("channel_type", "=", "gateway"),
                ("gateway_id", "=", gateway.id),
                ("gateway_channel_token", "=", self.gateway_channel_token),
            ],
            limit=1,
        )

    @api.model
    def _get_livechat_whatsapp_channel_vals(self, gateway, token, update):
        """Build channel vals for the livechat conversation channel paired to
        a WhatsApp gateway.

        The gateway (bot) channel is created by the base ``mail_gateway``
        module with ``channel_type='gateway'``. This method builds the
        ``channel_type='livechat'`` conversation channel where operators
        answer. It does NOT set ``gateway_id`` so that the automatic send
        handled by ``mail_gateway`` never fires on this channel: outbound
        messages are routed to the paired gateway channel instead.
        """
        livechat_channel = self._get_whatsapp_livechat_channel(gateway)
        if not livechat_channel:
            return {}
        user_operator = livechat_channel._get_operator()
        if not user_operator:
            _logger.warning("No livechat operator available for gateway %s", gateway.id)
            return {}
        author = self.env["mail.gateway.whatsapp"]._get_author(gateway, update)
        name = token
        for contact in update.get("contacts", []):
            if contact.get("wa_id") == token:
                name = contact.get("profile", {}).get("name", token)
                break
        member_partner_ids = set(gateway.member_ids.partner_id.ids)
        member_partner_ids.add(user_operator.partner_id.id)
        member_cmds = [
            Command.create({"partner_id": partner_id, "unpin_dt": False})
            for partner_id in member_partner_ids
        ]
        if author:
            if author._name == "res.partner":
                if author.id not in member_partner_ids:
                    member_cmds.append(Command.create({"partner_id": author.id}))
            elif author._name == "mail.guest":
                member_cmds.append(Command.create({"guest_id": author.id}))
        channel_name = " ".join(
            filter(
                None,
                [
                    name,
                    user_operator.livechat_username or user_operator.name,
                ],
            )
        )
        return {
            "name": channel_name,
            "channel_type": "livechat",
            "livechat_active": True,
            "livechat_channel_id": livechat_channel.id,
            "livechat_operator_id": user_operator.partner_id.id,
            "gateway_channel_token": token,
            "anonymous_name": name,
            "channel_member_ids": member_cmds,
            "company_id": gateway.company_id.id or False,
        }

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, *, message_type="notification", **kwargs):
        """Route messages on WhatsApp-related livechat channels.

        - On a ``livechat`` channel linked to a WhatsApp gateway, outbound
          messages create a single gateway notification pointing to the paired
          gateway (bot) channel, so they are sent through WhatsApp. A copy is
          mirrored to the gateway channel so gateway administrators see the
          full thread.
        - On a ``gateway`` channel linked to a WhatsApp livechat channel,
          messages are forwarded normally. Duplicate prevention is handled by
          the ``no_gateway_notification`` context flag already set by callers
          that should not trigger sends (webhook inbound, mirrored replies).
        """
        is_livechat_whatsapp = (
            self.channel_type == "livechat"
            and self.livechat_channel_id
            and self.livechat_channel_id.whatsapp_gateway_id
        )
        if is_livechat_whatsapp:
            message = super().message_post(message_type=message_type, **kwargs)
            if (
                message.message_type != "notification"
                and not self.env.context.get("no_gateway_notification")
            ):
                gateway = self.livechat_channel_id.whatsapp_gateway_id
                gateway_channel = self.sudo()._get_whatsapp_gateway_channel()
                if gateway_channel:
                    self.env["mail.notification"].sudo().create(
                        {
                            "mail_message_id": message.id,
                            "gateway_channel_id": gateway_channel.id,
                            "notification_type": "gateway",
                            "gateway_type": gateway.gateway_type,
                        }
                    ).send_gateway()
                    gateway_channel.sudo().with_context(
                        no_gateway_notification=True
                    ).message_post(
                        body=message.body,
                        attachment_ids=message.attachment_ids.ids,
                        subtype_xmlid=message.subtype_id.xml_id,
                        author_id=message.author_id.id,
                        message_type="comment",
                    )
            return message
        return super().message_post(message_type=message_type, **kwargs)