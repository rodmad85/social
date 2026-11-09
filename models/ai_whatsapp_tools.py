# -*- coding: utf-8 -*-
# Copyright 2026 Madooit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
import unicodedata
from datetime import date, datetime, timedelta

from odoo import api, models
from odoo.tools import html2plaintext

from odoo.addons.ai_tool.tools import aitool

_logger = logging.getLogger(__name__)

# Respostas que significam "qualquer opção" para uma variável
ANY_ANSWERS = (
    "qualquer",
    "qualquer um",
    "qualquer uma",
    "tanto faz",
    "indiferente",
    "nao importa",
    "o que tiver",
    "todos",
    "todas",
    "ns",
)

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _norm(text):
    """Normaliza texto para comparação (minúsculas, sem acentos)."""
    if not text:
        return ""
    text = " ".join(str(text).split()).lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _squash(text):
    """Como ``_norm``, mas sem espaços ('30 minutos' -> '30minutos')."""
    return _norm(text).replace(" ", "")


def _match_value(answer, options):
    """Retorna a opção que corresponde à resposta, ou ``None``.

    ``"*"`` significa "qualquer opção".
    """
    ans = _squash(answer)
    if not ans:
        return None
    if ans in {_squash(a) for a in ANY_ANSWERS}:
        return "*"
    options_sq = [(_squash(o), o) for o in options]
    # correspondência exata primeiro
    for squash_opt, original in options_sq:
        if squash_opt == ans:
            return original
    # correspondência parcial ("30" em "30min", "com a Ariani" em "Ariani")
    for squash_opt, original in options_sq:
        if squash_opt and (squash_opt in ans or ans in squash_opt):
            return original
    return None


def _parse_date(value):
    """Converte string de data nos formatos aceitos (AAAA-MM-DD, DD/MM/AAAA...)."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


class DiscussChannelAiWhatsappTools(models.Model):
    _inherit = "discuss.channel"

    @aitool(
        input_schema={
            "date_from": {
                "type": "string",
                "description": "Data inicial (AAAA-MM-DD ou DD/MM/AAAA). Padrão: hoje.",
            },
            "date_to": {
                "type": "string",
                "description": "Data final (AAAA-MM-DD ou DD/MM/AAAA). Padrão: 7 dias após a inicial.",
            },
            "professional_id": {
                "type": "integer",
                "description": "ID do profissional (opcional).",
            },
        },
        output_schema={
            "slots": {"type": "array", "items": {"type": "object"}},
        },
    )
    @api.model
    def ai_whatsapp_tool_get_availability(self, date_from=None, date_to=None, professional_id=None, **kwargs):
        """Tool: consulta horários disponíveis via clinical_management."""
        date_from = _parse_date(date_from) or date.today()
        date_to = _parse_date(date_to) or (date_from + timedelta(days=7))

        if professional_id:
            try:
                professional_id = int(professional_id)
            except (TypeError, ValueError):
                professional_id = False

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

    def _ai_whatsapp_save_price_ctx(self, key, filtros):
        """Grava a memória de variáveis já respondidas pelo cliente."""
        if not self:
            return
        try:
            self.sudo().write(
                {
                    "ai_price_ctx": json.dumps(
                        {"servico": key, "filtros": filtros}, ensure_ascii=False
                    )
                }
            )
        except Exception:
            _logger.exception("Failed to save AI price context on channel %s", self.id)

    @aitool(
        input_schema={
            "search_term": {
                "type": "string",
                "description": "Nome do procedimento/serviço (ex: fonoaudiologia, psicologia).",
            },
            "tempo": {
                "type": "string",
                "description": "Variável 'Tempo' (ex: 30min, 45min, 60min). Só envie se o cliente já informou.",
            },
            "periodo": {
                "type": "string",
                "description": "Variável 'Período' (ex: Avulso, Mensal, Trimestral, Semestral, 15 Sessões). Só envie se o cliente já informou.",
            },
            "profissional": {
                "type": "string",
                "description": "Variável 'Profissional' (ex: Ariani, Outros). Só envie se o cliente já informou.",
            },
            "resposta": {
                "type": "string",
                "description": "Mensagem mais recente do cliente respondendo a uma pergunta sobre variável do procedimento.",
            },
        },
        output_schema={
            "servico": {"type": "string"},
            "variaveis": {"type": "object"},
            "respostas": {"type": "object"},
            "pendentes": {"type": "array", "items": {"type": "string"}},
            "proxima_pergunta": {"type": "object"},
            "items": {"type": "array", "items": {"type": "object"}},
            "instrucao": {"type": "string"},
        },
        required_inputs=["search_term"],
    )
    def ai_whatsapp_tool_get_prices(
        self,
        search_term=None,
        tempo=None,
        periodo=None,
        profissional=None,
        resposta=None,
        limit=50,
        **kwargs,
    ):
        """Tool: preços de procedimentos, perguntando as variáveis uma a uma.

        Se o procedimento tem variáveis (atributos com várias opções, ex.:
        Tempo, Período, Profissional), devolve ``proxima_pergunta`` para a IA
        perguntar ao cliente; só devolve preços quando todas as variáveis
        estiverem respondidas. As respostas são memorizadas em
        ``ai_price_ctx`` para não depender da memória do modelo.
        """
        try:
            limit = int(limit) if limit else 50
        except (TypeError, ValueError):
            limit = 50

        def _fail(msg, **extra):
            result = {
                "servico": search_term or "",
                "variaveis": {},
                "respostas": {},
                "pendentes": [],
                "proxima_pergunta": None,
                "items": [],
                "instrucao": msg,
            }
            result.update(extra)
            return result

        key = _norm(search_term)
        if not key:
            return _fail(
                "search_term ausente. Peça ao cliente o nome do procedimento/serviço."
            )

        # ---------- contexto salvo (memória entre mensagens) ----------
        ctx = {}
        if self:
            raw = self.sudo().ai_price_ctx
            if raw:
                try:
                    ctx = json.loads(raw) or {}
                except Exception:
                    ctx = {}
        filtros = dict(ctx.get("filtros") or {}) if ctx.get("servico") == key else {}

        # ---------- tabela de preços padrão ----------
        Pricelist = self.env["product.pricelist"]
        pricelist = Pricelist.search(
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
            pricelist = Pricelist.search([("active", "=", True)], limit=1, order="id asc")
        if not pricelist:
            return _fail("Não existe tabela de preços ativa. Transfira para um atendente humano.")

        # ---------- localizar procedimento ----------
        templates = self.env["product.template"].search(
            [("name", "ilike", search_term)], limit=10
        )
        best = self.env["product.template"]
        for tmpl in templates:
            name = _norm(tmpl.name)
            if name == key or key in name or name in key:
                best = tmpl
                break
        if not best and templates:
            best = templates[0]
        if not best:
            return _fail(
                "Procedimento não encontrado na tabela de preços. "
                "Transfira para um atendente humano.",
                alternativas=[],
            )
        alternativas = [t.name for t in (templates - best)]

        # ---------- variáveis (atributos com mais de uma opção) ----------
        variables = {}
        attr_keys = {}
        for line in best.attribute_line_ids:
            options = list(line.value_ids.mapped("name"))
            if len(options) > 1:
                variables[line.attribute_id.name] = options
                attr_keys[_norm(line.attribute_id.name)] = line.attribute_id.name

        # ---------- coletar respostas fornecidas ----------
        named = []
        for hint, value in (("tempo", tempo), ("periodo", periodo), ("profissional", profissional)):
            if value:
                named.append((hint, value))
        for k, v in kwargs.items():
            if v:
                named.append((_norm(k), v))
        answer = resposta
        if not answer and self:
            # fallback: última mensagem do próprio cliente no canal
            ai_partner = self.env.ref("base.partner_root", raise_if_not_found=False)
            last_msgs = self.env["mail.message"].search(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", self.id),
                    ("message_type", "=", "comment"),
                ],
                order="id desc",
                limit=3,
            )
            for m in last_msgs:
                if ai_partner and m.author_id == ai_partner:
                    continue
                body = html2plaintext(m.body or "").strip()
                if body:
                    answer = body
                    break

        # ---------- resolver respostas ----------
        for hint, value in named:
            if hint not in attr_keys:
                continue
            matched = _match_value(value, variables[attr_keys[hint]])
            if matched is not None:
                filtros[hint] = matched
        if answer:
            # primeiro nas variáveis ainda pendentes, depois nas já respondidas
            for passo in ("pendentes", "respondidas"):
                for name in variables:
                    nkey = _norm(name)
                    respondida = nkey in filtros
                    if passo == "pendentes" and respondida:
                        continue
                    if passo == "respondidas" and not respondida:
                        continue
                    matched = _match_value(answer, variables[name])
                    if matched is not None:
                        filtros[nkey] = matched
                        break
                else:
                    continue
                break

        # ---------- variáveis pendentes ----------
        pendentes = []
        respostas = {}
        for name in variables:
            nkey = _norm(name)
            if nkey in filtros:
                respostas[name] = "Qualquer" if filtros[nkey] == "*" else filtros[nkey]
            else:
                pendentes.append(name)

        currency = pricelist.currency_id
        moeda = currency.name if currency else ""

        if pendentes:
            first = pendentes[0]
            self._ai_whatsapp_save_price_ctx(key, filtros)
            return {
                "servico": best.name,
                "moeda": moeda,
                "variaveis": variables,
                "respostas": respostas,
                "pendentes": pendentes,
                "proxima_pergunta": {"variavel": first, "opcoes": variables[first]},
                "items": [],
                "alternativas": alternativas,
                "instrucao": (
                    "O procedimento '%s' tem variáveis e ainda falta: %s. "
                    "NÃO informe preço ainda. Pergunte ao cliente apenas '%s' "
                    "(opções: %s). Quando ele responder, chame a ferramenta de novo "
                    "com search_term='%s' e resposta=<mensagem do cliente>."
                )
                % (best.name, first, first, ", ".join(variables[first]), search_term),
            }

        # ---------- filtrar combinações e calcular preços ----------
        variants = best.product_variant_ids
        for name in variables:
            nkey = _norm(name)
            chosen = filtros.get(nkey)
            if not chosen or chosen == "*":
                continue
            target = _squash(chosen)
            variants = variants.filtered(
                lambda v, nkey=nkey, target=target: any(
                    _norm(ptav.attribute_id.name) == nkey
                    and _squash(ptav.product_attribute_value_id.name) == target
                    for ptav in v.product_template_attribute_value_ids
                )
            )

        items = []
        sem_regra = 0
        for variant in variants:
            price = None
            na_tabela = True
            try:
                price, rule_id = pricelist._get_product_price_rule(variant, 1.0)
                na_tabela = bool(rule_id)
            except Exception:
                price = variant.list_price
                na_tabela = False
            if not na_tabela:
                sem_regra += 1
            variation = " / ".join(
                ptav.product_attribute_value_id.name
                for ptav in variant.product_template_attribute_value_ids
            )
            items.append(
                {
                    "variacao": variation,
                    "preco": round(float(price or 0.0), 2),
                    "na_tabela": na_tabela,
                }
            )
            if len(items) >= limit:
                break

        instrucao = "Informe os preços ao cliente usando 'variacao' e 'preco'."
        if not items:
            instrucao = (
                "Nenhuma combinação encontrada com as opções escolhidas. "
                "Confirme as opções disponíveis com o cliente."
            )
        elif sem_regra:
            instrucao += (
                " %d combinação(ões) sem preço específico na tabela (foi usado o "
                "valor padrão): avise que o valor precisa ser confirmado com a "
                "recepção." % sem_regra
            )

        self._ai_whatsapp_save_price_ctx(key, filtros)
        return {
            "servico": best.name,
            "moeda": moeda,
            "variaveis": variables,
            "respostas": respostas,
            "pendentes": [],
            "proxima_pergunta": None,
            "items": items,
            "alternativas": alternativas,
            "instrucao": instrucao,
        }
