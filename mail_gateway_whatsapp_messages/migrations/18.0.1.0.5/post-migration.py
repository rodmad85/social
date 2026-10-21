# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _get_keeper(env, channel):
    """Retorna o usuário responsável atual da conversa.

    Ordem de prioridade:

    1. Vendedor da oportunidade (``crm.lead.user_id``) vinculada à conversa;
    2. Último usuário interno que enviou mensagem WhatsApp no canal;
    3. Nenhum (a conversa fica não atribuída).
    """
    link = (
        env["mail.whatsapp.chatter.link"]
        .sudo()
        .search(
            [("channel_id", "=", channel.id), ("res_model", "=", "crm.lead")],
            limit=1,
        )
    )
    if link:
        lead = env["crm.lead"].sudo().browse(link.res_id).exists()
        if lead and lead.user_id and lead.user_id.active:
            return lead.user_id

    env.cr.execute(
        """
        SELECT ru.id
        FROM mail_message ms
        JOIN res_users ru ON ru.partner_id = ms.author_id
        WHERE ms.model = 'discuss.channel'
          AND ms.res_id = %s
          AND ms.gateway_type = 'whatsapp'
          AND ms.author_id IS NOT NULL
          AND ru.active = TRUE
        ORDER BY ms.date DESC
        LIMIT 1
        """,
        (channel.id,),
    )
    row = env.cr.fetchone()
    if row:
        return env["res.users"].sudo().browse(row[0]).exists()
    return env["res.users"]


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Channel = env["discuss.channel"].sudo()
    Member = env["discuss.channel.member"].sudo()

    channels = Channel.search(
        [
            ("channel_type", "=", "gateway"),
            ("gateway_id.gateway_type", "=", "whatsapp"),
        ]
    )
    removed_members = 0
    reassigned_channels = 0

    for channel in channels:
        internal_members = channel.channel_member_ids.filtered(
            lambda member: member.partner_id.user_ids.filtered("active")
        )
        if not internal_members:
            continue

        keeper = _get_keeper(env, channel)
        keeper_partner = keeper.partner_id if keeper else env["res.partner"]
        if keeper_partner and not keeper.has_group("mail_gateway.gateway_user"):
            # Sem o grupo Gateway o usuário não consegue abrir a conversa;
            # nesse caso a conversa volta para a lista de não atribuídas.
            keeper_partner = env["res.partner"]

        to_remove = internal_members.filtered(
            lambda member: not keeper_partner or member.partner_id != keeper_partner
        )
        if to_remove:
            removed_members += len(to_remove)
            to_remove.unlink()

        if keeper_partner and not channel.channel_member_ids.filtered(
            lambda member: member.partner_id == keeper_partner
        ):
            Member.create(
                {
                    "channel_id": channel.id,
                    "partner_id": keeper_partner.id,
                    "is_pinned": False,
                    "unpin_dt": False,
                }
            )
            reassigned_channels += 1

    _logger.info(
        "WhatsApp: %s membro(s) interno(s) removido(s) de conversas antigas; "
        "%s conversa(s) reatribuída(s) ao responsável.",
        removed_members,
        reassigned_channels,
    )
