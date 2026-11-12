O módulo **WhatsApp Central Settings** centraliza, em um único local do menu
**Definições**, as principais configurações dos módulos de WhatsApp das pastas
`social` e `whatsappcall`.

## Principais configurações

* **Recebimento de ligações — quem deverá receber:** usuários responsáveis por
  receber ligações do WhatsApp.
* **Efetuar ligações — quem pode efetuar:** usuários autorizados a efetuar
  ligações via WhatsApp.
* **Editar templates de mensagem — quem pode editar:** usuários autorizados a
  criar/editar mensagens template do WhatsApp.
* **Mensagens não atribuídas:** definem se vão para a lista de mensagens ou são
  atribuídas diretamente a um usuário (com usuário padrão opcional).
* **Quem pode ver o menu WhatsApp - Conversas:** grupos que podem ver o menu
  WhatsApp - Conversas no módulo Mensagens (Discuss).

Os valores são armazenados em parâmetros do sistema (`ir.config_parameter`).

## Observação sobre o módulo de chamada

Os módulos da pasta `whatsappcall` (`odoo_whatsapp_calling`,
`tus_meta_whatsapp_base`, `tus_meta_wa_discuss`) não estão no
`addons_path` deste ambiente, portanto este módulo **não depende** deles. A
configuração de recebimento de ligações é salva no parâmetro do sistema e
será sincronizada com `provider.wa_call_responsible_user_ids` quando o módulo
de chamada estiver instalado.
