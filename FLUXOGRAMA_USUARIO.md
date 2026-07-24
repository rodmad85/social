# Como funciona o envio e recebimento de mensagens pelo WhatsApp
### Explicação simplificada para o usuário

---

## 1. Quando você recebe uma mensagem do WhatsApp

1. **A Meta (WhatsApp) envia um aviso automático para o Odoo**
   Sempre que alguém manda uma mensagem para o seu número comercial, o WhatsApp envia um aviso para o Odoo. Esse aviso inclui o número de quem enviou, o texto da mensagem, quaisquer fotos/anexos e, se for uma resposta, qual mensagem original está sendo respondida.

2. **O Odoo procura (ou cria) um chat para esse número**
   O sistema verifica se aquele número de telefone já está vinculado a algum contato cadastrado. Ele tenta várias formas de encontrar o contato:
   - Primeiro, verifica se existe um vínculo conhecido (telefone já registrado antes).
   - Depois, busca pelo número com e sem o código do país (+55).
   - Se ainda não encontrar, tenta casar apenas pelos últimos 8 dígitos (útil para números brasileiros longos).
   - Finalmente, verifica o campo de WhatsApp do contato, caso exista.

3. **Se não encontrar o contato no sistema**
   Se nenhum contato cadastrado corresponder ao número, o Odoo cria um "visitante anônimo" (guest) com o nome do perfil do WhatsApp. Essa mensagem fica visível apenas no chat do gateway, sem ser vinculada a nenhum cliente ou registro de negócio.

4. **A mensagem aparece no chat do canal do gateway**
   O texto, anexos e link de localização (se houver) são postados no canal de WhatsApp como uma mensagem normal.

5. ** automaticamente o Odoo "espelha" essa mensagem nos registros de negócio vinculados**
   Quando existe um vínculo entre o chat do WhatsApp e um registro (por exemplo, um lead ou pedido de venda), a mensagem é copiada automaticamente para o chatter (feed de atividades) desse registro. Isso acontece em tempo real.

6. **Se o chat acabou de ser vinculado a um registro pela primeira vez**
   O Odoo também reproduz todas as mensagens antigas que já existiam no chat, para que fiquem visíveis no chatter do registro.

7. **Se ninguém estiver acompanhando aquele chat**
   Quando uma mensagem chega de um número desconhecido e nenhum vendedor está ativo naquele chat, o sistema avisa os gerentes de vendas e SDRs, para que alguém assuma a conversa.

---

## 2. Quando você envia uma mensagem pelo WhatsApp

1. **Você inicia o envio de duas formas**
   - **Pelo chatter de um registro** (lead, pedido de venda etc.): ao clicar no botão de WhatsApp no registro, abre um pequeno formulário onde você escolhe o telefone do contato e escreve a mensagem.
   - **Pelo chat do gateway**: você pode digitar diretamente no canal de WhatsApp do gateway.

2. **O Odoo resolve para qual número enviar**
   O sistema identifica o telefone selecionado (celular, telefone fixo ou número específico do WhatsApp do contato), sanitiza (remove o + e formata) e encontra ou cria o canal de chat correspondente.

3. **Verificação de permissão**
   Se o registro tem um vendedor atribuído, apenas esse vendedor (ou um gerente) pode enviar mensagens WhatsApp por aquele registro. Caso contrário, o Odoo bloqueia o envio com uma mensagem de erro.

4. **A mensagem é postada no canal do WhatsApp**
   O texto e anexos são enviados ao canal interno. Se for um template pré-aprovado do WhatsApp, o sistema verifica se já não enviou o mesmo template nas últimas 24 horas sem que o contato tenha respondido (para evitar bloqueios por spam).

5. **O Odoo envia a mensagem para a Meta (WhatsApp)**
   A integração faz uma chamada à API do WhatsApp (Meta Graph API):
   - Para textos: envia o corpo da mensagem convertido de HTML para texto puro.
   - Para anexos (imagem, áudio, vídeo, documento, adesivo): faz upload do arquivo primeiro e depois envia a mensagem com a mídia.
   - Templates: envia no formato de template com as variáveis substituídas.

6. **O status da mensagem é atualizado**
   - Se o envio foi bem-sucedido, a mensagem no Odoo é marcada como "enviada" e recebe o ID de confirmação do WhatsApp.
   - Se houve erro, a mensagem é marcada como "falha" com o motivo, e o usuário é notificado.

7. **A mensagem também é copiada para o chatter do registro de negócio**
   Assim como no recebimento, a mensagem enviada é espelhada automaticamente no chatter do lead, pedido de venda ou outro registro vinculado. Os demais usuários acompanhando aquele registro recebem uma notificação em tempo real sobre a nova mensagem.

---

## 3. Resumo do ciclo completo

```
WhatsApp (Meta)                  Odoo                              Registro de Negócio
     │                               │                                      │
     │  webhook com nova mensagem    │                                      │
     ├─────────────────────────────►│                                      │
     │                               │  1. Encontra/cria canal de chat     │
     │                               │  2. Resolve o autor (contacto)      │
     │                               │  3. Se guest → registro como        │
     │                               │     visitante anônimo               │
     │                               │  4. Posta mensagem no canal          │
     │                               │                                      │
     │                               │  5. Copia para o chatter do          │
     │                               │     registro vinculado               │
     │                               │     (lead, ordem de venda, etc.)    │
     │                               │  6. Notifica seguidores em           │
     │                               │     tempo real                       │
     │                               │                                      │
     │                               │                                      │
     ◄───────────────────────────────┤  7. Usuário envia mensagem          │
     │                               │  8. Verifica permissões             │
     │                               │  9. Envia via API do WhatsApp       │
     │                               │ 10. Atualiza status (enviado/erro)  │
     │                               │ 11. Copia para chatter do registro   │
     │                               │ 12. Notifica seguidores              │
     │   confirmação de entrega      │                                      │
     ◄───────────────────────────────┤──────────────────────────────────────┘
```

---

## 4. O que acontece quando o contato NÃO é identificado?

| Situação | O que o Odoo faz |
|----------|-------------------|
| Número não encontrado em nenhum contato do sistema | Cria um "visitante anônimo" (guest) com o nome do perfil do WhatsApp |
| A mensagem fica apenas no chat do gateway | Não aparece no chatter de nenhum registro de negócio |
| Nenhum vendedor está acompanhando o chat | O sistema envia um aviso para os gerentes de vendas/SDRs |
| Alguém clica no chat e vincula manualmente | A partir daí, novas mensagens são espelhadas no chatter do registro vinculado |
| Mensagens antigas do canal | Quando o vínculo é criado, todas as mensagens anteriores são reproduzidas no chatter do registro |

---

## 5. Proteções e regras importantes

- **Rate limiting de templates**: Não é permitido enviar o mesmo template WhatsApp para o mesmo contato dentro de 24 horas, a menos que o contato tenha respondido no intervalo.
- **Restrição por vendedor**: Se um registro tem um vendedor atribuído, apenas esse vendedor ou um gerente pode enviar mensagens WhatsApp por aquele registro.
- **Sincronização automática**: Quando uma nova ligação é feita entre um chat do WhatsApp e um registro de negócio, todas as mensagens históricas são automaticamente reproduzidas no chatter.
- **Notificações em tempo real**: Todos os usuários que acompanham o registro ou o canal recebem atualizações instantâneas quando uma nova mensagem é enviada ou recebida.

---
