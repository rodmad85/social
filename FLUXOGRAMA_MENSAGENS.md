# Fluxograma: Envio e Recebimento de Mensagens
## Módulos `mail_gateway_whatsapp_chatter` e `mail.message`

---

## 1. FLUXO DE RECEBIMENTO (WhatsApp ➜ Odoo)

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. WEBHOOK CHEGA DO WHATSAPP (Meta)                               │
│  POST /gateway/whatsapp/<token>/update                              │
│  ↳ gateway/controllers/gateway.py → GatewayController.post_update() │
│  ↳ Verifica assinatura HMAC (x-hub-signature-256)                   │
│  ↳ Chama dispatcher._receive_update(gateway, jsonrequest)           │
└──────────────────────────┬──────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  2. _receive_update() (mail_gateway_whatsapp)                       │
│  Itera sobre entry → changes → messages                             │
│  Para cada mensagem:                                                │
│    a) Extrai `from` (telefone do remetente)                         │
│    b) Extrai `context.id` (mensagem replying, se houver)            │
│    c) Chama _get_channel(gateway, token, update, force_create=True) │
│    d) Chama _process_update(chat, message, value)                   │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  3. CHATTER: _get_channel() OVERRIDE                                │
│  (mail_gateway_whatsapp_chatter/models/mail_gateway_whatsapp.py)    │
│                                                                      │
│  Estratégia de resolução do canal (discuss.channel):                │
│                                                                      │
│  ┌─ Tentativa 1: token como-isso (com + e sem +)                   │
│  │  gateway._get_channel_id(token) ou gateway._get_channel_id(+token)│
│  │  Encontrou? → Retorna o canal existente                          │
│  │                                                              │
│  ├─ Tentativa 2: transformações brasileiras (12 e 13 dígitos)     │
│  │  12 dígitos (ex: 5511999999999) → tenta 5511999999999          │
│  │  13 dígitos (ex: 5511999999999) → tenta 5511999999999          │
│  │  Encontrou? → Retorna o canal existente                          │
│  │                                                              │
│  ├─ Tentativa 3: resolve autor → busca res.partner.gateway.channel │
│  │  Chama _get_author(gateway, update)                              │
│  │  Se autor = res.partner:                                         │
│  │    → Procura res.partner.gateway.channel                         │
│  │      (partner_id, gateway_id, gateway_token)                    │
│  │    Se existe: retorna o canal vinculado ao parceiro              │
│  │    Se não existe: tenta usar gateway_token do parceiro           │
│  │    Se não encontrar nada: cai no super() → cria novo canal       │
│  │                                                              │
│  └─Fallback: super()._get_channel() (base do mail_gateway)          │
│     Cria novo discuss.channel "gateway"                             │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  4. CHATTER: _get_author() — RESOLUÇÃO DE CONTATO                  │
│  (mail_gateway_whatsapp_chatter/models/mail_gateway_whatsapp.py)    │
│  Ordem de prioridade:                                               │
│                                                                      │
│  ┌─① res.partner.gateway.channel (ligação conhecida)               │
│  │  Busca por gateway_id + gateway_token (telefone do WhatsApp)    │
│  │  Encontrou? → Retorna o partner_id vinculado                    │
│  │                                                              │
│  ├─② phone_sanitized = "+" + telefone                              │
│  │  Busca res.partner.where phone_sanitized == "+5511999999999"    │
│  │  Encontrou? → Retorna o partner                                 │
│  │                                                              │
│  ├─③ phone_sanitized = telefone (sem +)                            │
│  │  Busca res.partner.where phone_sanitized == "5511999999999"     │
│  │  Encontrou? → Retorna o partner                                 │
│  │                                                              │
│  ├─④ Fuzzy: últimos 8 dígitos (Brasil 12/13 dígitos)              │
│  │  Tenta: 5511999999999 → last 8 = 99999999                       │
│  │  Busca phone_sanitized LIKE %99999999                          │
│  │  Encontrou? → Retorna o partner                                 │
│  │                                                              │
│  ├─⑤ whatsapp_phone (módulo mail_gateway_whatsapp_messages)        │
│  │  Busca res.partner.whatsapp_phone (campo do módulo messages)    │
│  │  Encontrou? → Retorna o partner                                 │
│  │                                                              │
│  ├─⑥ mail.guest (Guest fallback — contato NÃO identificado)       │
│  │  Busca mail.guest com mesmo gateway_token                       │
│  │  Existente? → Retorna o guest existente                         │
│  │  Não existe? → Cria novo mail.guest com nome do perfil WhatsApp│
│  │                 (dos dados contacts da webhook)                  │
│  │                 → guest.não tem partner_id → não vinculado      │
│  │  A mensagem é postada no canal com o GUEST como autor           │
│  │                                                              │
│  └─⑦ Se partner encontrado: cria res.partner.gateway.channel       │
│     (se ainda não existir) vinculando partner ↔ gateway ↔ token   │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  5. _process_update() (mail_gateway_whatsapp)                       │
│  Monta o conteúdo da mensagem:                                      │
│  ┌─ text → body                                                     │
│  ├─ image/audio/video/document/sticker → baixa via Facebook API    │
│  │  → cria attachment record                                        │
│  ├─ location → inline Google Maps link                              │
│  └─ contacts → ignorado                                             │
│                                                                      │
│  Chama:                                                              │
│    chat.sudo().message_post(                                         │
│      body=body,                                                      │
│      author_id=partner.id (ou False para guest),                    │
│      gateway_type="whatsapp",                                        │
│      message_type="comment",                                         │
│      subtype_xmlid="mail.mt_comment",                                │
│      attachments=attachments,                                        │
│      date=timestamp                                                  │
│    )                                                                 │
│                                                                      │
│  Se for reply (context.id):                                         │
│    → Liga como parent_id na mensagem original                       │
│    → Também posta no thread original vinculado                      │
│    → Atualiza gateway_message_id                                    │
│                                                                      │
│  Chama _post_process_message() (pós-processamento)                   │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  6. CHATTER: discuss.channel.message_post() — CÓPIA PARA CHATTER   │
│  (mail_gateway_whatsapp_chatter/models/discuss_channel.py)          │
│                                                                      │
│  Após super().message_post():                                       │
│  ┌─ Se é template WhatsApp → cria mail.whatsapp.template.send      │
│  │  (controle de rate limiting 24h)                                 │
│  │                                                              │
│  └─ Se é mensagem comment (não-template) E gateway_type=whatsapp:  │
│     → Chama mail.gateway.whatsapp._post_to_linked_threads()        │
│       (copia a mensagem para os threads vinculados no chatter!)     │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  7. _post_to_linked_threads() — CÓPIA PARA REGISTROS DE NEGÓCIO    │
│  (mail_gateway_whatsapp_chatter/models/mail_gateway_whatsapp.py)    │
│                                                                      │
│  Busca todos os mail.whatsapp.chatter.link para aquele canal:      │
│  ┌─ Para cada link:                                                 │
│  │  → Record = self.env[link.res_model].browse(link.res_id)        │
│  │  → Chama record.sudo().message_post(                             │
│  │      body=body,                                                   │
│  │      author_id=partner_id (se res.partner, senão False),        │
│  │      gateway_type="whatsapp",                                     │
│  │      message_type="comment",                                      │
│  │      subtype_xmlid="mail.mt_comment",                             │
│  │      attachment_ids=attachment_ids,                               │
│  │    )                                                              │
│  │                                                                  │
│  │  → Envia notificação em tempo real para todos os seguidores     │
│  │    ativos do registro via _bus_send_store()                      │
│  │    (tipo: mail.record/insert)                                    │
│  └─ Se o record não existir mais → ignora (continue)               │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  8. Sincronização histórica (quando link é criado pela 1ª vez)     │
│  (mail_gateway_whatsapp_chatter/models/mail_whatsapp_chatter_link.py)│
│                                                                      │
│  MailWhatsappChatterLink.get_or_create():                           │
│  ├─ Se link NÃO existe:                                             │
│  │  → Cria o link (channel_id, res_model, res_id, partner_id)      │
│  │  → Chama _sync_historical_messages()                             │
│  │                                                                  │
│  └─ _sync_historical_messages():                                    │
│     Pega todas as mensagens WhatsApp do canal (excluindo o         │
│     atual partner) já existentes, ordena por id e para cada uma:   │
│     → record.sudo().message_post(                                   │
│         body=m.body,                                                 │
│         author_id=partner.id,                                        │
│         gateway_type="whatsapp",                                     │
│         message_type="comment",                                      │
│         subtype_xmlid="mail.mt_comment",                             │
│         attachment_ids=m.attachment_ids.ids,                         │
│       )                                                              │
│     (Importante: usa sudo() para não verificar permissões)          │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  9. NOTIFICAÇÃO PARA CONVERSAS NÃO ATRIBUÍDAS                      │
│  (mail_gateway_whatsapp_chatter/models/mail_gateway_whatsapp.py)    │
│  _receive_update() → para cada telefone afetado:                   │
│  → _notify_unassigned(channel)                                      │
│  Se o canal NÃO tem nenhum usuário ativo como membro:              │
│    → Notifica managers/sales SDRs via message_post(                │
│        body="Nova conversa WhatsApp não atribuída de {name}",      │
│        message_type="notification",                                  │
│        partner_ids=users.partner_id.ids                             │
│      )                                                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. FLUXO DE ENVIO (Odoo ➜ WhatsApp)

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. USUÁRIO ENVIA MENSAGEM                                         │
│  Via um de dois caminhos:                                           │
│                                                                      │
│  CAMINHO A: WhatsAppComposer wizard (chatter)                       │
│  (mail_gateway_whatsapp_chatter/models/mail_message.py)             │
│  → Resolução do número:                                             │
│    ├─ whatsapp_N → busca res.partner.whatsapp_phone                 │
│    │  → sanitiza (remove +)                                        │
│    │  → cria res.partner.gateway.channel se não existir             │
│    │  → _get_channel() para encontrar/criar discuss.channel        │
│    │                                                              │
│    └─ mobile/phone → record._whatsapp_get_channel(phone, gateway)  │
│       → sanitiza, cria res.partner.gateway.channel,                │
│         cria/retorna discuss.channel                               │
│                                                                      │
│  → Cria mail.whatsapp.chatter.link entre channel e record          │
│  → Adiciona usuário atual como membro do canal (discuss.channel    │
│    member) se já não for                                           │
│  → channel.message_post(body=body, subtype=mail.mt_comment,        │
│    message_type="comment", whatsapp_template_id=...)               │
│                                                                      │
│  CAMINHO B: Via registro (sale.order, crm.lead, etc.)              │
│  → Usuário clica no botão WhatsApp no chatter do registro          │
│  → O quesapp.composer é aberto                                     │
│  → Seleciona telefone (mobile, phone, ou whatsapp_N)               │
│  → Segue mesmo fluxo do Caminho A                                  │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  2. CHATTER: discuss.channel.message_post()                        │
│  (mail_gateway_whatsapp_chatter/models/discuss_channel.py)          │
│                                                                      │
│  Após super().message_post():                                       │
│  ┌─ Se é template → cria mail.whatsapp.template.send               │
│  │  (registra para controle de rate limiting 24h)                  │
│  │                                                              │
│  └─ Se é comment E gateway_type=whatsapp E sem gateway_message_id: │
│     → Chama _post_to_linked_threads() → copia pro chatter do       │
│       registro de negócio (veremos abaixo)                        │
│     → Também NOTIFICA membros do canal em tempo real               │
│       via _bus_send_store() (mail.record/insert)                   │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  3. CAMINHO BASE: _send_to_gateway_thread()                        │
│  (mail_gateway/models/mail_message.py)                              │
│                                                                      │
│  Quando message_post() é chamado num registo com gateway_channel:  │
│  → Cria mail.notification com notification_type="gateway"          │
│  → notification_type="gateway" dispara a integração                │
│  → mail.notification.send_gateway() → delega para                  │
│    mail.gateway.whatsapp._send()                                    │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  4. CHATTER: _send() — VERIFICAÇÃO DE PERMISSÃO                    │
│  (mail_gateway_whatsapp_chatter/models/mail_gateway_whatsapp.py)    │
│                                                                      │
│  Se o record tem user_id diferente do usuário atual E               │
│  usuário NÃO é sales manager E NÃO é SDR:                          │
│  → Raise UserError: "Apenas o vendedor atribuído pode enviar       │
│    mensagens WhatsApp para este registro."                          │
│                                                                      │
│  Senão → super()._send() (chama a integração real)                 │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  5. mail.gateway.whatsapp._send() (BASE)                           │
│  (mail_gateway_whatsapp/models/mail_gateway_whatsapp.py)            │
│                                                                      │
│  Para cada anexo no mail_message_id:                                │
│  → Upload no Facebook Graph API (/media) → obtém media_id          │
│  → POST /messages com payload de mídia                              │
│                                                                      │
│  Se tem body de texto:                                              │
│  → POST /messages com payload de texto (HTML→plaintext)            │
│  → Pode usar template WhatsApp (se context.whatsapp_template_id)   │
│                                                                      │
│  Response:                                                           │
│  → Sucesso: Atualiza notification → notification_status="sent",    │
│    gateway_message_id=<id do Meta>                                  │
│  → Falha: Atualiza notification → notification_status="exception", │
│    failure_reason=<erro>, failure_type="unknown"                    │
│    → Notifica usuário da falha via _notify_message_notification    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. O QUE OCORRE QUANDO NÃO É IDENTIFICADO O CONTATO

```
┌─────────────────────────────────────────────────────────────────────┐
│  CENÁRIO: telefone do remetente NÃO encontrado em nenhum          │
│          res.partner (nem por gateway.channel, nem por             │
│          phone_sanitized, nem por fuzzy, nem por whatsapp_phone)  │
│                                                                      │
│  ┌─ mail.guest é CRIADO                                           │
│  │  (mail_gateway_whatsapp_chatter/models/mail_gateway_whatsapp.py │
│  │   _get_author(), passo ⑥)                                       │
│  │  • gateway_token = telefone do remetente                       │
│  │  • name = nome do perfil WhatsApp (dos contacts da webhook)    │
│  │  • NÃO tem partner_id → não está vinculado a nenhum contato    │
│  │  • É um "visitante" anônimo                                     │
│  │                                                              │
│  ├─ Mensagem é postada no discuss.channel com guest como author   │
│  │  → No chatter do Odoo, guest aparece como "Nome do WhatsApp"   │
│  │  → Sem vinculação a nenhum registro de negócio                 │
│  │                                                              │
│  ├─ _receive_update() (chatter) → _notify_unassigned(channel)     │
│  │  Verifica se há algum usuário ativo como membro do canal:      │
│  │  ├─ Se HÁ usuário ativo → não faz nada                        │
│  │  └─ Se NÃO HÁ usuário ativo:                                    │
│  │     → Busca sales managers + SDRs + "Líderes de Equipe"       │
│  │     → Envia mensagem de notificação no canal:                   │
│  │       "Nova conversa WhatsApp não atribuída de {name}"          │
│  │     → Apenas usuários com grupo gateway_user são notificados   │
│  │                                                              │
│  └─ O contato NUNCA aparece no chatter de nenhum registro de       │
│     negócio (não há mail.whatsapp.chatter.link para guest)        │
│     → Mensagem fica "presa" no discuss.channel do gateway         │
│     → Só aparece no chatter quando alguém vincula manualmente      │
│       (via whatsapp.composer ou transfer wizard)                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. RESUMO: CÓPIA MENSAGEM PARA O CHATTER

```
┌─────────────────────────────────────────────────────────────────┐
│  Quando uma mensagem WhatsApp CHEGA (incoming):                 │
│                                                                  │
│  chat.message_post() ──→ discuss.channel.message_post()        │
│                           │                                     │
│                           ├──→ super() → mensagem no canal      │
│                           │                                     │
│                           ├──→ if comment + whatsapp:           │
│                           │    _post_to_linked_threads()        │
│                           │      │                              │
│                           │      └─→ para cada link:            │
│                           │           record.sudo().message_post│
│                           │           (copia pro chatter do      │
│                           │            sale.order/lead/etc.)    │
│                           │           + notificação em tempo     │
│                           │             real para seguidores     │
│                           │                                     │
│                           └──→ if histórico (novo link):        │
│                                _sync_historical_messages()      │
│                                (replay de todas as mensagens    │
│                                 antigas do canal pro chatter)   │
│                                                                  │
│  Quando uma mensagem WhatsApp SAIR (outgoing):                  │
│  channel.message_post() (pelo composer) ──→ mesmo mecanismo    │
│  → super().message_post() → mensagem no canal                  │
│  → _post_to_linked_threads() → cópia pro chatter do registro   │
│  → NOTIFICAÇÃO em tempo real para seguidores do registro       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. MODELOS E RELAÇÕES CHAVE (Nomes Técnicos)

| Modelo (Odoo) | Módulo | Papel Técnico |
|---------------|--------|---------------|
| `ir.server.action` | `mail_gateway_whatsapp_chatter` | Ação de servidor estendida para disponibilizar modelos de e-mail com thread para actions state=whatsapp |
| `mail.gateway.abstract` | `mail_gateway` | Modelo abstrato base para serviços de gateway (canal, token, membros) |
| `mail.gateway.whatsapp` | `mail_gateway_whatsapp` | Serviço concreto de integração WhatsApp (recebimento webhook, envio via Meta Graph API, post-processamento) |
| `discuss.channel` | `mail` + `mail_gateway_whatsapp_chatter` | Canal de discussão (chat), estendido para suportar gateway e linked threads |
| `mail.message` | `mail` + `mail_gateway` + `mail_gateway_whatsapp_chatter` | Modelo central de mensagem; estendido com gateway_type, gateway_notification_ids, is_whatsapp_incoming, _send_to_gateway_thread |
| `res.partner` | `mail_gateway` + `mail_gateway_whatsapp_messages` | Parceiro/ contato; estendido com phone_sanitized, whatsapp_phone_ids, gateway_channel_ids |
| `res.partner.gateway.channel` | `mail_gateway` | Mapeamento many-to-one entre partner, gateway e token telefônico (identifica qual contato do WhatsApp pertence a qual partner) |
| `mail.guest` | `mail` | Visitante anônimo (fallback quando nenhum partner é encontrado); vinculado ao gateway e ao token |
| `mail.whatsapp.chatter.link` | `mail_gateway_whatsapp_chatter` | Relação única entre discuss.channel e registro de negócio (sale.order, crm.lead, etc.); aciona sincronização histórica |
| `mail.whatsapp.template.send` | `mail_gateway_whatsapp_chatter` | Registro de rastreamento de envio de template WhatsApp (controle de rate limiting 24h, estado waiting/responded/expired) |
| `mail.notification` | `mail` + `mail_gateway` | Notificação de entrega; notification_type="gateway" dispara a integração com o provedor WhatsApp |
| `mail.thread` | `mail` + `mail_gateway` + `mail_gateway_whatsapp_chatter` | Mixin de thread do Odoo; estendido para roteamento de notificações gateway e criação automática de canais |
| `mail.gateway.whatsapp` (service) | `mail_gateway_whatsapp_chatter` | Override de _send (restrição de permissão por user_id), _get_author (resolução de contato), _get_channel (roteamento de canal), _post_to_linked_threads (propagação para chatter)

---
