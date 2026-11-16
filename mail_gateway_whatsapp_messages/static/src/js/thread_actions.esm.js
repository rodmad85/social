/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {threadActionsRegistry} from "@mail/core/common/thread_actions";

/**
 * Sobrescreve a action "Open Contact" registrada por mail_gateway.
 *
 * Motivo: a implementacao original usa correspondent.persona.id como fallback
 * quando o canal ainda nao tem res.partner.gateway.channel (contato novo/guest).
 * Guest e partner tem sequencias de id independentes, entao o id do guest pode
 * apontar para um res.partner totalmente diferente (ex: guest 468 = Mauricio
 * Duarte, mas res.partner 468 = MARIA IVANILDE DE FIGUEIREDO ALVES).
 */
threadActionsRegistry.add(
    "open-gw-profile",
    {
        condition(component) {
            if (
                component.thread?.model !== "discuss.channel" ||
                (component.props.chatWindow && !component.props.chatWindow.isOpen)
            ) {
                return false;
            }
            if (component.thread._partnerIdChecked) {
                return Boolean(component.thread._cachedPartnerId);
            }
            const orm = component.env.services.orm;
            let partnerId = null;
            (async () => {
                const channelData = await orm.silent.searchRead(
                    "discuss.channel",
                    [["id", "=", component.thread.id]],
                    ["gateway_channel_token", "gateway_id"]
                );
                const channel = channelData[0];
                if (channel?.gateway_channel_token) {
                    // Filtra tambem pelo gateway_id: o mesmo token pode existir
                    // em configuracoes de gateways diferentes.
                    const domain = [["gateway_token", "=", channel.gateway_channel_token]];
                    const gatewayId = Array.isArray(channel.gateway_id)
                        ? channel.gateway_id[0]
                        : channel.gateway_id;
                    if (gatewayId) {
                        domain.push(["gateway_id", "=", gatewayId]);
                    }
                    const gatewayChannel = await orm.silent.searchRead(
                        "res.partner.gateway.channel",
                        domain,
                        ["partner_id"]
                    );
                    if (gatewayChannel[0]?.partner_id) {
                        partnerId = Array.isArray(gatewayChannel[0].partner_id)
                            ? gatewayChannel[0].partner_id[0]
                            : gatewayChannel[0].partner_id;
                    }
                }
                // NUNCA usar o id da persona quando ela for guest: guest e
                // partner tem sequencias de id independentes. Abrir res.partner
                // com o id do guest mostraria o contato errado.
                if (!partnerId) {
                    const persona = component.thread.correspondent?.persona;
                    if (persona && persona.type === "partner") {
                        partnerId = persona.id;
                    }
                }
                component.thread._cachedPartnerId = partnerId;
                component.thread._partnerIdChecked = true;
                component.render?.();
            })();
            return false;
        },
        icon: "fa fa-fw fa-user-circle-o",
        name: _t("Open Contact"),
        async open(component) {
            const partnerId = component.thread._cachedPartnerId;
            if (!partnerId) {
                return;
            }
            await component.env.services.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: partnerId,
                views: [[false, "form"]],
            });
        },
        iconLarge: "fa fa-fw fa-lg fa-user-circle-o",
        sequence: 17,
    },
    {force: true}
);