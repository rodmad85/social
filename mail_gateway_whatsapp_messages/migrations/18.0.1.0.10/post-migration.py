# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    GatewayChannel = env["res.partner.gateway.channel"].sudo()
    WhatsappPhone = env["res.partner.whatsapp.phone"].sudo()

    # Corrige associações incorretas em res.partner.gateway.channel causadas
    # pelo bug de busca parcial (últimos 8 dígitos) no _get_author.
    # Isso afetava conversas onde contatos com mesmos 8 últimos dígitos
    # (ex: DDDs diferentes) eram confundidos.
    wa_channels = GatewayChannel.search(
        [("gateway_id.gateway_type", "=", "whatsapp")]
    )
    _logger.info(
        "WhatsApp migration: verificando %s gateway_channels...", len(wa_channels)
    )

    fixed = 0
    for gc in wa_channels:
        token = (gc.gateway_token or "").replace("+", "")
        if not token:
            continue

        # Busca exata pelo phone_sanitized completo
        sanitized_token = "+" + token if not token.startswith("+") else token

        wp = WhatsappPhone.search(
            [("phone_sanitized", "=", sanitized_token)], limit=1
        )
        correct_partner = wp.partner_id if wp else False

        if not correct_partner:
            # Fallback: busca direta no res.partner
            partner = env["res.partner"].search(
                [("phone_sanitized", "=", sanitized_token)], limit=1
            )
            correct_partner = partner

        if correct_partner and gc.partner_id != correct_partner:
            _logger.info(
                "Corrigindo gateway_channel %s: token=%s, "
                "partner_errado=%s (%s) -> partner_correto=%s (%s)",
                gc.id,
                token,
                gc.partner_id.name,
                gc.partner_id.id,
                correct_partner.name,
                correct_partner.id,
            )
            gc.write({"partner_id": correct_partner.id})
            fixed += 1
        elif not correct_partner:
            _logger.warning(
                "Gateway_channel %s: token=%s - nenhum partner encontrado",
                gc.id,
                token,
            )

    # Sempre recria a view pois a SQL foi corrigida (match exato vs parcial)
    env["mail.whatsapp.conversation"].init()
    _logger.info("View mail_whatsapp_conversation recriada com SQL corrigido.")

    if fixed:
        _logger.info(
            "WhatsApp migration: %s gateway_channels corrigidos.", fixed
        )
    else:
        _logger.info("WhatsApp migration: nenhum gateway_channel precisou de correção.")