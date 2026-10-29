# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import Command, api, models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

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
    def _pick_least_loaded_user(self, users):
        """Return the user of ``users`` with the fewest open livechat
        conversations (ties broken by smallest id), or an empty recordset."""
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
        """Return ``(partner, display_name)`` to fill ``livechat_operator_id``.

        An *online* operator is preferred (standard livechat assignment), but
        WhatsApp conversations must keep working when nobody is connected:
        the fallback chain is

        1. an online operator of the livechat channel (``_get_operator``),
        2. the operators configured on the livechat channel (even offline),
        3. the members of the WhatsApp gateway (the people answering it),
        4. any user with the livechat operator group,
        5. finally the admin / company partner.

        Step 5 matters because Odoo forbids ``livechat`` channels without an
        operator (SQL constraint on ``livechat_operator_id``).
        """
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
        channel_name = " ".join(
            filter(
                None,
                [
                    name,
                    operator_name,
                ],
            )
        )
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

    # ------------------------------------------------------------------
    # WhatsApp chatbot (scripted questions)
    # ------------------------------------------------------------------
    @api.model
    def _whatsapp_chatbot_lang(self, conversation, author=False):
        """Language used by the scripted questions.

        The company language (pt_BR in most deployments) is used by default;
        an explicit language on the customer partner wins over it. Partners
        left on the Odoo default (en_US) do not override the company so the
        bot does not suddenly switch to English.
        """
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
            # the webhook dispatcher turns gateway notifications off (an
            # inbound message must never be echoed back to WhatsApp), but the
            # bot messages have to be sent to the customer
            "no_gateway_notification": False,
            # tags the posts made by the bot itself so that the takeover
            # detection below never stops the bot on its own messages
            "whatsapp_chatbot": True,
        }

    @api.model
    def _whatsapp_chatbot_start(self, conversation, author=False):
        """Post the script's welcome steps on the first WhatsApp contact.

        The steps posted here are regular messages on the livechat channel:
        they are mirrored to the gateway channel and sent to the customer by
        ``DiscussChannel.message_post``.
        """
        script = conversation.livechat_channel_id.whatsapp_chatbot_script_id
        if not script:
            return
        context = self._whatsapp_chatbot_context(conversation, author)
        channel = conversation.with_context(**context)
        try:
            script.with_context(**context)._post_welcome_steps(channel)
            step = channel.chatbot_current_step_id
            if step and step.step_type == "forward_operator":
                # the script opens on an operator handoff: run it right away
                self._whatsapp_chatbot_run(channel, step, "")
        except Exception:
            _logger.exception(
                "WhatsApp bot welcome steps failed on channel %s", conversation.id
            )

    @api.model
    def _whatsapp_chatbot_run(self, channel, step, message_body):
        """Post ``step`` and keep going while the bot talks on its own
        (``text`` steps). Stops the script when a human has to take over
        (``forward_operator``) or when it ends."""
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
        """Run the script after the customer answered the current step."""
        self.ensure_one()
        if not self.chatbot_current_step_id:
            return
        channel = self.with_context(**self._whatsapp_chatbot_context(self))
        step = channel.chatbot_current_step_id
        if step.step_type == "question_selection" and not selected_answer:
            # the customer typed something else than one of the options:
            # ask the question again so the options are shown once more
            self._whatsapp_chatbot_reask(channel, step)
            return
        try:
            next_step = step._process_answer(channel, message_body)
        except Exception:
            _logger.exception(
                "WhatsApp bot could not process the answer on channel %s", self.id
            )
            # invalid input (e.g. malformed email): display the question again
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
        """Turn the bot off so that humans can take over the conversation."""
        for channel in self:
            if channel.chatbot_current_step_id:
                channel.sudo().chatbot_current_step_id = False
                _logger.info(
                    "WhatsApp bot stopped on channel %s (%s)", channel.id, reason
                )

    def _whatsapp_paired_conversation(self):
        """Livechat conversation paired with this gateway (bot) channel."""
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
        """Stop the scripted bot as soon as a human writes in the thread.

        Two takeover paths are covered: replying on the livechat conversation
        and replying directly on the gateway (bot) channel, which is how
        attendants usually answer. Mirrored messages use the
        ``no_gateway_notification`` flag and never trigger the second path.
        """
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
        message = super().message_post(message_type=message_type, **kwargs)
        self._whatsapp_chatbot_check_takeover(message)
        if is_livechat_whatsapp:
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
                    mirror = gateway_channel
                    if message.author_guest_id:
                        # keep the visitor as author of the mirrored message
                        mirror = mirror.with_user(
                            self.env.ref("base.public_user").id
                        ).with_context(guest=message.author_guest_id)
                    mirror.sudo().with_context(no_gateway_notification=True).message_post(
                        body=message.body,
                        attachment_ids=message.attachment_ids.ids,
                        subtype_xmlid=self._get_subtype_xmlid(message.subtype_id),
                        author_id=message.author_id.id,
                        message_type="comment",
                    )
        return message

    @api.model
    def _get_subtype_xmlid(self, subtype):
        """Return the xmlid of a ``mail.message.subtype`` record.

        ``mail.message.subtype`` does not expose its xmlid in Odoo 18, so it
        is resolved through ``ir.model.data``. Defaults to ``mail.mt_comment``
        when the subtype has no xmlid (custom subtypes).
        """
        if not subtype:
            return "mail.mt_comment"
        imd = (
            self.env["ir.model.data"]
            .sudo()
            .search(
                [("model", "=", "mail.message.subtype"), ("res_id", "=", subtype.id)],
                limit=1,
            )
        )
        return f"{imd.module}.{imd.name}" if imd else "mail.mt_comment"