# -*- coding: utf-8 -*-
# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
from datetime import date, timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)


class DiscussChannelAiWhatsappTools(models.Model):
    _inherit = "discuss.channel"

    @api.model
    def ai_whatsapp_tool_get_availability(self, date_from=None, date_to=None, professional_id=None, **kwargs):
        """Tool: consulta horários disponíveis via clinical_management."""
        if not date_from:
            date_from = date.today()
        else:
            try:
                if isinstance(date_from, str):
                    date_from = date.fromisoformat(date_from)
            except Exception:
                date_from = date.today()

        if date_to:
            try:
                if isinstance(date_to, str):
                    date_to = date.fromisoformat(date_to)
            except Exception:
                date_to = None
        if not date_to:
            date_to = date_from + timedelta(days=7)

        availability_model = self.env["hospital.professional.availability"]
        if professional_id:
            professional = self.env["hr.employee"].browse(professional_id)
            if not professional.exists():
                return {"slots": []}
            slots = availability_model._build_professional_availability(
                professional, date_from=date_from, date_to=date_to
            )
        else:
            professionals = self.env["hr.employee"].search([("schedule_ids", "!=", False)])
            slots = availability_model.browse()
            for prof in professionals:
                slots |= availability_model._build_professional_availability(
                    prof, date_from=date_from, date_to=date_to
                )

        result = []
        for s in slots:
            try:
                hour = s.hour
                hour_int = int(hour)
                hour_min = int(round((hour - hour_int) * 60))
                time_str = "%02d:%02d" % (hour_int, hour_min)
            except Exception:
                time_str = str(s.hour)
            result.append(
                {
                    "data": s.session_date.isoformat() if s.session_date else False,
                    "hora": time_str,
                    "profissional_id": s.professional_id.id if s.professional_id else False,
                    "profissional_nome": s.professional_id.name if s.professional_id else "",
                    "sala": s.room_id.name if s.room_id else "",
                }
            )
        return {"slots": result}

    @api.model
    def ai_whatsapp_tool_get_prices(self, search_term=None, limit=10, **kwargs):
        """Tool: consulta tabela de preços padrão."""
        if not search_term:
            return {"items": []}
        limit = int(limit) if limit else 10
        pricelist = self.env["product.pricelist"].search(
            [
                ("active", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
            order="id asc",
        )
        if not pricelist:
            pricelist = self.env["product.pricelist"].search([("active", "=", True)], limit=1)
        if not pricelist:
            return {"items": []}

        items = self.env["product.pricelist.item"].search(
            [
                ("pricelist_id", "=", pricelist.id),
                "|",
                ("product_tmpl_id.name", "ilike", search_term),
                ("product_id.name", "ilike", search_term),
            ],
            limit=limit,
        )
        result = []
        currency = pricelist.currency_id
        for item in items:
            product_name = ""
            if item.product_tmpl_id:
                product_name = item.product_tmpl_id.name
            elif item.product_id:
                product_name = item.product_id.name
            price = item.fixed_price if item.compute_price == "fixed" else 0.0
            if item.compute_price == "percentage" and item.percent_price:
                price = item.percent_price
            result.append(
                {
                    "servico": product_name,
                    "preco": price,
                    "moeda": currency.name if currency else "",
                    "tipo": item.compute_price,
                }
            )
        return {"items": result}
