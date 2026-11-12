# Mail WhatsApp Gateway Chatter

**Versão:** 18.0.1.0.1  
**Licença:** AGPL-3  
**Autor:** Odoo Community Association (OCA)

---

## 1. Visão Geral

Este módulo integra o WhatsApp ao Chatter do Odoo, permitindo a sincronização bidirecional de mensagens entre conversas WhatsApp e registros de negócio (como leads CRM, pedidos de venda, etc.).

---

## 2. Funcionalidades Principais

- **Sincronização bidirecional** — Mensagens enviadas e recebidas via WhatsApp são automaticamente refletidas no Chatter do registro vinculado.
- **Interface estilizada** — Mensagens de WhatsApp exibidas como balões de chat (verde para mensagens próprias, branco para recebidas).
- **Indicadores de entrega** — Ícones de confirmação (visto simples, visto duplo, erro) nas mensagens.
- **Seleção de templates** — Permite escolher templates do WhatsApp ao enviar mensagens pelo Chatter.
- **Seleção de número de telefone** — Quando o contato possui múltiplos números WhatsApp, é possível escolher qual usar no envio.
- **Vinculação automática** — O canal WhatsApp é automaticamente vinculado ao registro ao enviar a primeira mensagem.
- **Sincronização histórica** — Mensagens anteriores do canal são copiadas para o Chatter quando o vínculo é criado.
- **Solicitação de transferência** — Usuários podem solicitar transferência de conversas para outros atendentes, com fluxo de aprovação por administradores.

---

## 3. Fluxo de Funcionamento

### 3.1 Mensagem Recebida (WhatsApp → Chatter)

1. Uma mensagem WhatsApp chega ao gateway.
2. O gateway localiza ou cria um canal `discuss.channel` do tipo `"gateway"`.
3. A mensagem é postada no canal.
4. O módulo busca todos os registros `mail.whatsapp.chatter.link` vinculados ao canal.
5. Para cada registro vinculado, a mensagem é copiada ao Chatter com `gateway_type="whatsapp"`.
6. Os seguidores do registro são notificados via bus.

### 3.2 Mensagem Enviada (Chatter → WhatsApp)

1. O usuário ativa o botão WhatsApp no Chatter.
2. Se o contato possui múltiplos números WhatsApp, um seletor de canais é exibido para escolher qual número usar.
3. Opcionalmente seleciona um template de mensagem.
4. Digita a mensagem e envia.
5. O sistema localiza ou cria o canal WhatsApp para o registro.
6. A mensagem é enviada via WhatsApp.
7. O canal é automaticamente vinculado ao registro via `get_or_create()`.

### 3.3 Vinculação de Canal a Registro

Ao vincular um canal a um registro (primeiro envio), o sistema:
1. Cria um registro em `mail.whatsapp.chatter.link` com o modelo e ID do registro.
2. Sincroniza mensagens históricas do canal para o Chatter do registro.

### 3.4 Identificação de Autor

Quando uma mensagem WhatsApp chega, o sistema identifica o autor na seguinte ordem:
1. Busca por `res.partner.gateway.channel` com o token exato.
2. Busca por `phone_sanitized` no `res.partner`.
3. Busca por `phone_sanitized` com normalização do 9 dígito (BR).
4. Se não encontrado, cria um `mail.guest` para o número desconhecido.

---

## 4. Modelos de Dados

### 4.1 `mail.whatsapp.chatter.link`

Vincula um canal `discuss.channel` a um registro de negócio.

| Campo | Tipo | Descrição |
|---|---|---|
| `channel_id` | Many2one(`discuss.channel`) | Canal do gateway |
| `res_model` | Char | Modelo do registro (ex.: `crm.lead`) |
| `res_id` | Integer | ID do registro |
| `partner_id` | Many2one(`res.partner`) | Parceiro associado |
| `display_name` | Char (compute) | Nome exibido: `"{channel} - {registro}"` |

**Restrição:** `UNIQUE(channel_id, res_model, res_id)` — um canal só pode ser vinculado uma vez ao mesmo registro.

### 4.2 `mail.notification` (estendido)

| Campo | Tipo | Descrição |
|---|---|---|
| `whatsapp_template_id` | Many2one(`mail.whatsapp.template`) | Template usado na notificação |

### 4.3 `mail.message` (estendido)

| Campo | Tipo | Descrição |
|---|---|---|
| `is_whatsapp_incoming` | Boolean | True se `gateway_type == "whatsapp"` e o autor não é o parceiro atual |

### 4.4 `crm.lead` (não ativado)

| Campo | Tipo | Descrição |
|---|---|---|
| `whatsapp_channel_id` | Many2one(`discuss.channel`, compute) | Canal WhatsApp vinculado ao lead |

---

## 5. Segurança e Restrições

### 5.1 Acesso a Dados

**Grupo:** `mail_gateway.gateway_user`

| Modelo | Permissões |
|---|---|
| `mail.whatsapp.chatter.link` | Leitura, Escrita, Criação, Exclusão |

### 5.2 Regra de Registro

**Canais `discuss.channel`:**
- Usuários do grupo `gateway_user` podem **apenas** ver e escrever em canais dos quais são membros.
- Não podem criar ou excluir canais.

### 5.3 Restrição de Envio

**Apenas o vendedor designado pode enviar WhatsApp.**

Se o registro vinculado possuir um campo `user_id` definido para um usuário diferente do atual, o sistema **bloqueia o envio** com a mensagem:
> "Only the assigned salesperson can send WhatsApp messages for this record."

Exceções:
- Usuários do grupo `sales_team.group_sale_manager`
- Usuários do grupo `crm_commissions.group_crm_commission_sdr`

### 5.4 Transferência de Conversa

- Usuários do grupo `gateway_user` podem **solicitar** transferência para outro usuário.
- Apenas usuários do grupo `base.group_system` (administradores) podem **aprovar ou rejeitar** transferências.
- O usuário de destino deve pertencer ao grupo `gateway_user`.

### 5.5 Uso de `sudo()`

O módulo utiliza `sudo()` em operações internas de sincronização para evitar violações das regras de registro, garantindo que mensagens sejam corretamente copiadas entre canais e Chatters independentemente das permissões do usuário atual.

---

## 6. Funcionalidades não Ativadas

Os seguintes arquivos existem no código-fonte mas **não estão carregados** no módulo (não constam no `__manifest__.py` ou `__init__.py`):

| Arquivo | Funcionalidade |
|---|---|
| `models/crm_lead.py` | Campo `whatsapp_channel_id` em leads CRM e botão "Reivindicar Conversa WhatsApp" |
| `models/ir_websocket.py` | Inscrição automática em canais gateway para atualizações em tempo real |
| `views/crm_lead_views.xml` | Botão estatístico WhatsApp no formulário de lead |
| `views/transfer_channel_views.xml` | Interface de transferência no formulário do canal |
| `views/transfer_wizard_views.xml` | Formulário do assistente de transferência |

Para ativar, adicione os imports em `models/__init__.py` e as entradas em `data` no `__manifest__.py`.

---

## 7. Dependências

| Módulo | Função |
|---|---|
| `mail` | Framework de Chatter e mensagens |
| `mail_gateway` | Modelo abstrato de gateway, canais e grupo `gateway_user` |
| `mail_gateway_whatsapp` | Integração específica WhatsApp, templates e composer |
| `sales_team` | Grupos de permissão de vendas |
| `crm_commissions` | Grupo de permissão SDR |

---

## 8. Customizações na Interface

- **Botão WhatsApp no Chatter** — Alterna entre modo texto e modo WhatsApp.
- **Balões de mensagem** — Verde (autor), Branco (recebida), com alinhamento lateral.
- **Indicadores de entrega** — Ícone de visto simples (enviado), duplo azul (visualizado), X vermelho (erro).
- **Seletor de canais** — Dropdown para escolher qual número WhatsApp usar quando o contato possui múltiplos telefones.
- **Seletor de templates** — Dropdown para escolher template WhatsApp ao enviar.
- **Domínio de templates** — Filtra templates por gateway, estado "aprovado" e modelo compatível.
- **Checkbox "Conversa iniciada"** — Indica se já existe uma conversa WhatsApp ativa para o canal.

---

## 9. Arquitetura Técnica

### 9.1 Identificação de Canal por Múltiplos Telefones

O método `_whatsapp_get_channel` em `mail_message.py` busca um `res.partner.gateway.channel` pelo trio `(partner_id, gateway_id, gateway_token)`. Se não existir, cria um novo registro, permitindo que um mesmo contato tenha múltiplos canais (um para cada número).

### 9.2 Sincronização via `_thread_to_store`

O método `_thread_to_store` garante que todos os canais gateway do parceiro (incluindo números alternativos) sejam enviados ao cliente para exibição no seletor de canais.

### 9.3 `_get_channel` no Recebimento

Quando uma mensagem chega com um token diferente do esperado, o método `_get_channel` em `mail_gateway_whatsapp.py` tenta primeiro buscar pelo token exato. Se não encontrar, busca por um canal do mesmo parceiro (identificado via `_get_author`), permitindo que diferentes números do mesmo contato caiam no mesmo canal.
