# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Janela usada para considerar que uma mensagem já existe no canal mantido.
DATE_TOLERANCE_SECONDS = 60


def _find_duplicate(message, kept_messages):
    for candidate in kept_messages:
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


def _copy_message(env, message, channel):
    """Repost a message on another channel without sending it to WhatsApp."""
    target = channel.sudo()
    author_id = message.author_id.id or False
    guest = message.author_guest_id
    if guest:
        target = (
            channel.with_user(env.ref("base.public_user").id)
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


def _ensure_member(env, channel, member):
    if not member:
        return
    domain = [("channel_id", "=", channel.id)]
    if member.partner_id:
        domain.append(("partner_id", "=", member.partner_id.id))
    else:
        domain.append(("guest_id", "=", member.guest_id.id))
    existing = env["discuss.channel.member"].sudo().search(domain, limit=1)
    if not existing:
        env["discuss.channel.member"].sudo().create(
            {
                "channel_id": channel.id,
                "partner_id": member.partner_id.id or False,
                "guest_id": member.guest_id.id or False,
                "unpin_dt": False,
            }
        )
    elif existing.unpin_dt:
        existing.write({"unpin_dt": False})


def _merge_channel(env, keeper, duplicate):
    Message = env["mail.message"].sudo()
    kept_messages = Message.search(
        [("model", "=", "discuss.channel"), ("res_id", "=", keeper.id)]
    )
    duplicate_messages = Message.search(
        [
            ("model", "=", "discuss.channel"),
            ("res_id", "=", duplicate.id),
            ("message_type", "=", "comment"),
        ],
        order="id",
    )
    moved = 0
    for message in duplicate_messages:
        if _find_duplicate(message, kept_messages):
            continue
        kept_messages |= _copy_message(env, message, keeper)
        moved += 1
    for member in duplicate.channel_member_ids:
        _ensure_member(env, keeper, member)
    link_vals = {}
    for field in ("livechat_channel_id", "livechat_operator_id", "anonymous_name"):
        if getattr(keeper, field) or not getattr(duplicate, field):
            continue
        value = getattr(duplicate, field)
        link_vals[field] = value.id if field != "anonymous_name" else value
    if link_vals:
        keeper.write(link_vals)
    duplicate.active = False
    return moved


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Channel = env["discuss.channel"].sudo()

    cr.execute(
        """
        SELECT gateway_id, gateway_channel_token, array_agg(id ORDER BY id)
        FROM discuss_channel
        WHERE channel_type = 'gateway'
          AND active
          AND gateway_channel_token IS NOT NULL
          AND gateway_channel_token != ''
        GROUP BY gateway_id, gateway_channel_token
        HAVING count(*) > 1
        """
    )
    groups = cr.fetchall()

    moved_messages = 0
    archived_channels = 0
    for _gateway_id, token, channel_ids in groups:
        channels = Channel.browse(channel_ids)
        # Keep the conversation with more messages, then the oldest one.
        counts = {
            channel.id: env["mail.message"]
            .sudo()
            .search_count(
                [("model", "=", "discuss.channel"), ("res_id", "=", channel.id)]
            )
            for channel in channels
        }
        keeper = max(channels, key=lambda c: (counts[c.id], -c.id))
        for duplicate in channels - keeper:
            moved_messages += _merge_channel(env, keeper, duplicate)
            archived_channels += 1
        _logger.info(
            "WhatsApp: merged %s duplicate gateway channel(s) for token %s into "
            "channel %s.",
            len(channels) - 1,
            token,
            keeper.id,
        )

    _logger.info(
        "WhatsApp: %s duplicate gateway channel(s) archived; %s message(s) moved.",
        archived_channels,
        moved_messages,
    )
