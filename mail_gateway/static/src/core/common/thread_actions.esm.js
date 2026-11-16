import {_t} from "@web/core/l10n/translation";
import {threadActionsRegistry} from "@mail/core/common/thread_actions";

threadActionsRegistry
    .add("open-gw-new-partner", {
        condition(component) {
            const thread = component.thread;
            if (
                thread?.model !== "discuss.channel" ||
                (component.props.chatWindow && !component.props.chatWindow.isOpen)
            ) {
                return false;
            }
            if (thread._guestChecked) {
                return Boolean(thread._cachedGuestId);
            }
            const orm = component.env.services.orm;
            (async () => {
                const members = await orm.silent.searchRead(
                    "discuss.channel.member",
                    [["channel_id", "=", thread.id]],
                    ["guest_id"]
                );
                const guestMembers = members.filter((m) => m.guest_id);

                if (guestMembers.length === 1) {
                    thread._cachedGuestId = guestMembers[0].guest_id;
                } else {
                    thread._cachedGuestId = null;
                }
                thread._guestChecked = true;
                component.render?.();
            })();
            return false;
        },
        icon: "fa fa-fw fa-address-book",
        name: _t("New Partner"),
        async open(component) {
            const guestId = component.thread._cachedGuestId;
            if (!guestId) return;
            await component.env.services.action.doAction({
                type: "ir.actions.act_window",
                res_model: "mail.guest.manage",
                context: {default_guest_id: guestId[0]},
                views: [[false, "form"]],
                target: "new",
            });
        },
        iconLarge: "fa fa-fw fa-lg fa-address-book",
        sequence: 18,
    })
    .add("open-gw-profile", {
        condition(component) {
            // Check basic conditions
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
                // partner tem sequencias de id independentes (ex: guest 468 =
                // Mauricio Duarte, mas partner 468 = outra pessoa). Abrir
                // res.partner com esse id mostraria o contato errado.
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
            await component.env.services.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: partnerId,
                views: [[false, "form"]],
            });
        },
        iconLarge: "fa fa-fw fa-lg fa-user-circle-o",
        sequence: 17,
    });
