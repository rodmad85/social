/** @odoo-module **/
/**
 * Remove o atalho "Client" do cabecalho do Discuss registrado por
 * tus_meta_wa_discuss (thread_actions.js, key "agent-list").
 *
 * Motivo: o painel desse atalho abre res.partner usando o id da persona do
 * correspondent. Para contatos novos o correspondent e um mail.guest, e guest
 * e partner tem sequencias de id independentes (ex: guest 468 = Mauricio
 * Duarte, mas res.partner 468 = MARIA IVANILDE DE FIGUEIREDO ALVES).
 *
 * Como o botao so abria o registro errado, ele e removido. O atalho
 * "Open Contact" do mail_gateway continua disponivel para contatos ja
 * convertidos em partner.
 */
import { threadActionsRegistry } from "@mail/core/common/thread_actions";
// Importa explicitamente o modulo do vendor para garantir que o add("agent-list")
// seja executado antes do remove (a ordem de definicao dos odoo.define importa).
import "@tus_meta_wa_discuss/js/agents/thread_actions";

threadActionsRegistry.remove("agent-list");
