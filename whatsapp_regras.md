# Regras de Envio de Mensagens WhatsApp - Política da Meta

## Política de 24 Horas da Meta/WhastApp

### A Regra Exata
A Meta/WhastApp **não libera automaticamente** o envio após 24 horas. A política é:

1. **Janela de 24 horas**: A partir da última mensagem **do cliente** (resposta), o negócio tem exatamente 24 horas para enviar mensagens
2. **Após 24h sem resposta**: O sistema **bloqueia** imediatamente o envio de novas mensagens
3. **Não há "periodo de graça"** ou "tempão" após os 24h
4. **Para retomar**: O cliente precisa enviar uma **nova mensagem**, o que reinicia o cronômetro de 24h

### Na Prática (Do que vemos nos logs)
```
[131047] Message failed to send because more than 24 hours have passed since the customer last replied to this number.
```

### O Que Isso Significa:
- ❌ **Após 24h sem resposta do cliente**: Envío BLOQUEADO imediatamente
- ❌ **Não dá para enviar** mensagem alguma (template ou texto)
- ❌ **Não tem período de "espera"** ou "tempão" após os 24h
- ❌ **Para enviar novamente**: Cliente precisa responder primeiro

### Como Funciona o Ciclo:
1. **Cliente responde** → Cronômetro de 24h inicia
2. **Nos próximos 24h**: Pode enviar mensagens (templates ou texto)
3. **Passados 24h sem resposta** → Envíos bloqueados automaticamente
4. **Cliente envia nova mensagem** → Cronômetro reinicia (24h novos)

### Para o Caso Viviane Madureira:
Como não houve conversa recente, o sistema bloqueou o envio após passar do período de 24h sem resposta. Isso é **esperado e correto** - não é falha do Odoo, mas da política da Meta/WhastApp.

### Para Retomar o Envio:
1. Peça para o cliente (Viviane) enviar primeira mensagem para o número do WhatsApp
2. Aguarde 24 horas após ela responder
3. Depois pode enviar mensagens (templates ou texto) dentro do período de 24h

### Resumo da Política:

| Situação | Pode Enviar? |
|----------|--------------|
| Cliente respondeu nas últimas 24h | ✅ Sim |
| Cliente não respondeu nas últimas 24h | ❌ Bloqueado |
| Cliente respondeu há mais de 24h | ❌ Bloqueado (até responder novamente) |

**Não existe "periodo de liberação" após 24h** - a única forma de retomar é o cliente responder.