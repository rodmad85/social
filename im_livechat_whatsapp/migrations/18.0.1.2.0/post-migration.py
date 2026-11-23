# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Janela usada para considerar que uma mensagem da livechat já foi espelhada
# no canal gateway.
DATE_TOLERANCE_SECONDS = 60


def _find_duplicate(message, gateway_messages):
    for candidate in gateway_messages:
        if candidate.message_type != message.message_type:
            continue
        if (candidate.body or "") != (message.body or ""):
            continue
        if (candidate.author_id.id or 0) != (message.author_id.id or 0):
            continue
        if (candidate.author_guest_id.id or 0) != (message.author_guest_id.id or 0):
            continue
        if not candidate.date or not message.date:
            return True
        delta = abs((candidate.date - message.date).total_seconds())
        if delta <= DATE_TOLERANCE_SECONDS:
            return True
    return False


def _copy_message(env, message, gateway_channel):
    """Repost a livechat message on the gateway channel without sending it."""
    target = gateway_channel.sudo()
    author_id = message.author_id.id or False
    guest = message.author_guest_id
    if guest:
        target = (
            gateway_channel.with_user(env.ref("base.public_user").id)
            .sudo()
            .with_context(guest=guest, no_gateway_notification=True)
        )
        author_id = False
    else:
        target = target.with_context(no_gateway_notification=True)
    return target.message_post(
        body=message.body,
        author_id=author_id,
        date=message.date,
        subtype_xmlid="mail.mt_comment",
        message_type="comment",
        attachment_ids=message.attachment_ids.ids,
        gateway_type="whatsapp",
    )


def _ensure_member(env, channel, partner):
    if not partner:
        return
    member = (
        env["discuss.channel.member"]
        .sudo()
        .search(
            [("channel_id", "=", channel.id), ("partner_id", "=", partner.id)],
            limit=1,
        )
    )
    if not member:
        env["discuss.channel.member"].sudo().create(
            {
                "channel_id": channel.id,
                "partner_id": partner.id,
                "unpin_dt": False,
            }
        )
    elif member.unpin_dt:
        member.write({"unpin_dt": False})


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Channel = env["discuss.channel"].sudo()
    Message = env["mail.message"].sudo()
    PartnerGateway = env["res.partner.gateway.channel"].sudo()

    livechat_channels = Channel.search(
        [
            ("channel_type", "=", "livechat"),
            ("gateway_channel_token", "!=", False),
            ("livechat_channel_id.whatsapp_gateway_id", "!=", False),
        ]
    )
    copied_messages = 0
    archived_channels = 0

    for livechat in livechat_channels:
        livechat_config = livechat.livechat_channel_id
        gateway = livechat_config.whatsapp_gateway_id
        gateway_channel = Channel.search(
            [
                ("channel_type", "=", "gateway"),
                ("gateway_id", "=", gateway.id),
                ("gateway_channel_token", "=", livechat.gateway_channel_token),
            ],
            limit=1,
        )
        if not gateway_channel:
            _logger.warning(
                "WhatsApp: no gateway channel found for livechat channel %s "
                "(token %s); skipping merge.",
                livechat.id,
                livechat.gateway_channel_token,
            )
            continue

        # Move messages that were never mirrored to the gateway channel.
        gateway_messages = Message.search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", gateway_channel.id),
            ]
        )
        livechat_messages = Message.search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", livechat.id),
                ("message_type", "=", "comment"),
            ],
            order="id",
        )
        for message in livechat_messages:
            if _find_duplicate(message, gateway_messages):
                continue
            gateway_messages |= _copy_message(env, message, gateway_channel)
            copied_messages += 1

        # Keep the operators and gateway members on the surviving channel.
        operator = livechat.livechat_operator_id
        if not operator and livechat_config.user_ids:
            operator = livechat_config.user_ids[:1].partner_id
        for partner in gateway.member_ids.partner_id | operator:
            _ensure_member(env, gateway_channel, partner)

        # Link the gateway conversation to the livechat configuration used by
        # the WhatsApp AI/chatbot and store the operator.
        link_vals = {}
        if not gateway_channel.livechat_channel_id:
            link_vals["livechat_channel_id"] = livechat_config.id
        if operator and not gateway_channel.livechat_operator_id:
            link_vals["livechat_operator_id"] = operator.id
        if not gateway_channel.anonymous_name:
            link_vals["anonymous_name"] = (
                livechat.anonymous_name or gateway_channel.name
            )
        if link_vals:
            gateway_channel.write(link_vals)

        # Registered contacts use the Odoo contact name.
        gateway_partner = PartnerGateway.search(
            [
                ("gateway_id", "=", gateway.id),
                ("gateway_token", "=", livechat.gateway_channel_token),
            ],
            limit=1,
        ).partner_id
        if gateway_partner and gateway_channel.name != gateway_partner.name:
            gateway_channel.name = gateway_partner.name

        # Hide the duplicated livechat conversation without unlinking it.
        if livechat.active:
            livechat.active = False
            archived_channels += 1

    _logger.info(
        "WhatsApp: %s message(s) moved to gateway channels; %s livechat "
        "channel(s) archived.",
        copied_messages,
        archived_channels,
    )
