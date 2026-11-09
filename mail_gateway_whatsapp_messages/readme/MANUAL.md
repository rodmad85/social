# Mail WhatsApp Gateway Messages

**Versão:** 18.0.1.0.2  
**Licença:** AGPL-3  
**Autor:** Odoo Community Association (OCA)

---

## 1. Visão Geral

Este módulo estende o `mail_gateway_whatsapp_chatter` adicionando uma interface de listagem de conversas WhatsApp, suporte a múltiplos telefones por contato, atribuição inteligente de conversas e vinculação a oportunidades CRM.

---

## 2. Funcionalidades Principais

- **Lista de Conversas** — Visualização de todas as conversas WhatsApp agrupadas por contato, com última mensagem, data e status.
- **Filtro de Não Atribuídas** — Visualização dedicada para conversas sem usuário responsável.
- **Atribuição Automática por Telefone** — Associa automaticamente conversas a parceiros e usuários com base no número de telefone.
- **Atribuição Manual de Contato** — Permite vincular uma conversa a um contato (`res.partner`) mesmo que o número seja diferente do principal.
- **Atribuição de Usuário** — Permite designar manualmente um usuário como responsável pela conversa.
- **Vínculo com Oportunidade CRM** — Permite vincular a conversa a uma oportunidade existente ou criar uma nova, copiando mensagens históricas.
- **Múltiplos Telefones por Contato** — Cadastro de números WhatsApp alternativos para um mesmo contato.
- **Identificação por Telefone Alternativo** — Reconhece automaticamente mensagens de números alternativos do contato.
- **Líder de Equipe** — Atribui automaticamente conversas não identificadas ao líder da equipe de vendas.
- **Nome do Canal Descritivo** — Quando um número alternativo é detectado, o canal exibe o nome do contato com a descrição do telefone entre parênteses.

---

## 3. Fluxo de Funcionamento

### 3.1 Recebimento de Mensagem

1. Mensagem chega ao gateway WhatsApp.
2. `_get_author` identifica o autor:
   - Busca primeiro em `res.partner.gateway.channel` pelo token exato.
   - Se não encontrar, busca em `res.partner.phone_sanitized` (com normalização do 9 para números BR).
   - Se não encontrar, busca em `res.partner.whatsapp.phone` (telefones alternativos).
   - Se encontrado em telefones alternativos, cria automaticamente o `res.partner.gateway.channel`.
3. `_receive_update` executa pós-processamento:
   - Atualiza o nome do canal com o nome do parceiro e a descrição do telefone alternativo (ex.: "João Silva (Escritório)").
   - Se o autor não foi identificado como parceiro, chama `_assign_team_lead` para adicionar o líder de equipe ao canal.
4. `_post_to_linked_threads` copia a mensagem para o Chatter de todos os registros vinculados.

### 3.2 Atribuição de Contato

1. Na lista de conversas não atribuídas, clique em "Atribuir Contato".
2. Selecione ou crie um contato (`res.partner`).
3. O wizard:
   - Se o número da conversa for diferente do telefone principal do contato, cria um registro em `res.partner.whatsapp.phone`.
   - Cria o mapeamento `res.partner.gateway.channel`.
   - Adiciona o contato como membro do canal.
   - Se existia um `mail.guest` vinculado ao canal, remove o guest e o associa ao parceiro.

### 3.3 Atribuição Automática por Telefone

1. Na lista de conversas, clique em "Buscar Contato".
2. O sistema executa SQL bulk para associar canais a parceiros cujo `phone_sanitized` corresponda ao token do canal.
3. A associação respeita a lógica de normalização do 9 dígito para números brasileiros.

### 3.4 Vínculo com Oportunidade CRM

1. Na lista de conversas não atribuídas e sem vínculo com CRM, clique em "Vincular Oportunidade".
2. Escolha uma oportunidade existente ou digite um nome para criar uma nova.
3. O wizard:
   - Cria a oportunidade (`crm.lead`) se necessário, associando o contato da conversa.
   - Cria o `mail.whatsapp.chatter.link` entre o canal e a oportunidade.
   - Copia todas as mensagens WhatsApp anteriores para o Chatter da oportunidade.
   - Adiciona o usuário atual como membro do canal.

### 3.5 Envio com Múltiplos Telefones

1. No Chatter, o seletor de canais exibe todos os números WhatsApp do contato.
2. O usuário escolhe qual número usar para o envio.
3. O método `_thread_to_store` (no módulo `mail_gateway_whatsapp_messages`) garante que números alternativos cadastrados em `res.partner.whatsapp.phone` tenham seus `res.partner.gateway.channel` criados automaticamente antes de serem enviados ao front-end.

---

## 4. Modelos de Dados

### 4.1 `res.partner.whatsapp.phone`

Telefones WhatsApp alternativos para um contato.

| Campo | Tipo | Descrição |
|---|---|---|
| `partner_id` | Many2one(`res.partner`) | Contato |
| `phone` | Char | Número de telefone |
| `phone_sanitized` | Char (compute, store) | Número sanitizado (apenas dígitos) |
| `description` | Char | Descrição (ex.: "Escritório", "Celular reserva") |

**Restrição:** `UNIQUE(partner_id, phone)` — cada telefone só pode ser cadastrado uma vez por contato.

### 4.2 `mail.whatsapp.conversation` (SQL View)

Visão SQL que agrupa mensagens WhatsApp por canal, com informações de contato e status.

| Campo | Tipo | Descrição |
|---|---|---|
| `channel_id` | Many2one(`discuss.channel`) | Canal da conversa |
| `partner_id` | Many2one(`res.partner`) | Contato identificado (por telefone ou autor) |
| `author_partner_id` | Many2one(`res.partner`) | Autor da última mensagem |
| `author_user_id` | Many2one(`res.users`) | Usuário dono do autor |
| `gateway_id` | Many2one(`mail.gateway`) | Gateway |
| `last_message_date` | Datetime | Data da última mensagem |
| `last_message_body` | Text | Corpo da última mensagem |
| `message_count` | Integer | Total de mensagens |
| `phone` | Char | Token do canal (número de telefone) |
| `is_unassigned` | Boolean | True se não há usuário ativo como membro do canal |
| `partner_user_id` | Many2one(`res.users`) | Usuário do contato identificado |
| `display_name` | Char | Nome do destinatário (contato > canal > "WhatsApp") |
| `has_crm_lead` | Boolean | True se existe `mail.whatsapp.chatter.link` para `crm.lead` |

### 4.3 `whatsapp.assign.contact.wizard`

Wizard para atribuir um contato a uma conversa.

| Campo | Tipo | Descrição |
|---|---|---|
| `partner_id` | Many2one(`res.partner`) | Contato a atribuir |
| `channel_id` | Many2one(`discuss.channel`) | Canal da conversa |
| `phone` | Char | Número de telefone (readonly) |

### 4.4 `whatsapp.link.opportunity.wizard`

Wizard para vincular uma conversa a uma oportunidade CRM.

| Campo | Tipo | Descrição |
|---|---|---|
| `channel_id` | Many2one(`discuss.channel`) | Canal da conversa |
| `partner_id` | Many2one(`res.partner`) | Contato da conversa |
| `existing_opportunity_id` | Many2one(`crm.lead`) | Oportunidade existente |
| `new_opportunity_name` | Char | Nome para criar nova oportunidade |

---

## 5. Segurança

### 5.1 Acesso a Dados

**Grupo:** `mail_gateway.gateway_user`

| Modelo | Permissões |
|---|---|
| `mail.whatsapp.conversation` | Leitura |
| `res.partner.whatsapp.phone` | Leitura, Escrita, Criação, Exclusão |
| `whatsapp.assign.contact.wizard` | Leitura, Escrita, Criação, Exclusão |
| `whatsapp.link.opportunity.wizard` | Leitura, Escrita, Criação, Exclusão |
| `whatsapp.assign.conversation.wizard` | Leitura, Escrita, Criação, Exclusão |

### 5.2 Menus

Os menus "WhatsApp → Conversas" e "WhatsApp → Não Atribuídas" são visíveis apenas para o grupo `sales_team.group_sale_manager`.

---

## 6. Arquitetura Técnica

### 6.1 SQL View `mail.whatsapp.conversation`

A view é recriada na inicialização do módulo (`init()`) e:
- Agrupa mensagens por canal usando `DISTINCT ON`.
- Identifica o contato via `phone_sanitized` com normalização do 9 dígito.
- Determina `is_unassigned` verificando ausência de membros ativos (usuários).
- Determina `has_crm_lead` via LEFT JOIN com `mail_whatsapp_chatter_link`.
- Após recriar a view, executa `action_auto_assign_by_phone()` para associar canais a usuários automaticamente.

### 6.2 Identificação de Autor com Múltiplos Telefones

O método `_get_author` no módulo `mail_gateway_whatsapp_messages` estende o comportamento do `mail_gateway_whatsapp_chatter`:
1. Chama `super()._get_author()` que busca por `gateway_channel` → `phone_sanitized`.
2. Se o autor não foi encontrado como parceiro (retornou guest), busca em `res.partner.whatsapp.phone` com normalização do 9 dígito.
3. Se encontrado, cria o `res.partner.gateway.channel` e retorna o parceiro.

### 6.3 Criação Automática de Gateway Channels

O método `_get_gateway_follower_partners` (em `mail_thread.py`) intercepta a chamada do Chatter para garantir que parceiros com `whatsapp_phone_ids` tenham todos os seus `res.partner.gateway.channel` criados antes que a interface do Chatter seja carregada.

### 6.4 Líder de Equipe

`_assign_team_lead` busca o grupo "Líderes de Equipe de Vendas" e adiciona o primeiro usuário ativo como membro do canal, se o canal não possuir nenhum membro ativo.

---

## 7. Interface

### 7.1 Lista de Conversas

A árvore de conversas exibe:
- Autor, Destinatário, Última Mensagem, Quantidade.
- Ícone "Não atribuída" (boleano).
- Botão "Abrir Conversa" — sempre visível.
- Botão "Buscar Contato" — apenas para não atribuídas.
- Botão "Atribuir Contato" — apenas para não atribuídas (cor verde).
- Botão "Vincular Oportunidade" — apenas para não atribuídas sem CRM (cor laranja).

### 7.2 Aba "WhatsApp Phones" no Contato

No formulário do contato (`res.partner`), uma página "WhatsApp Phones" permite cadastrar números alternativos com descrição.

---

## 8. Dependências

| Módulo | Função |
|---|---|
| `mail` | Framework de Chatter e mensagens |
| `mail_gateway` | Modelo abstrato de gateway |
| `mail_gateway_whatsapp_chatter` | Sincronização Chatter-WhatsApp e modelo `mail.whatsapp.chatter.link` |
| `sales_team` | Grupo de gerentes de vendas para menus |
