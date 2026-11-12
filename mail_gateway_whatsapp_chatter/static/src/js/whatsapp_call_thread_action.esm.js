import {_t} from "@web/core/l10n/translation";
import {threadActionsRegistry} from "@mail/core/common/thread_actions";

threadActionsRegistry
    .add("whatsapp-call", {
        condition(component) {
            const thread = component.thread;
            if (
                thread?.model !== "discuss.channel" ||
                (component.props.chatWindow && !component.props.chatWindow.isOpen)
            ) {
                return false;
            }
            return Boolean(thread?.whatsapp_channel);
        },
        icon: "fa fa-fw fa-phone",
        iconLarge: "fa fa-fw fa-lg fa-phone",
        name: _t("Iniciar Chamada"),
        async open(component) {
            let partnerId = component.thread.correspondent?.persona?.id;
            if (!partnerId) {
                const channelData = await component.env.services.orm.silent.searchRead(
                    "discuss.channel",
                    [["id", "=", component.thread.id]],
                    ["gateway_channel_token"]
                );
                if (channelData[0]?.gateway_channel_token) {
                    const gatewayChannel = await component.env.services.orm.silent.searchRead(
                        "res.partner.gateway.channel",
                        [["gateway_token", "=", channelData[0].gateway_channel_token]],
                        ["partner_id"]
                    );
                    partnerId = Array.isArray(gatewayChannel[0]?.partner_id)
                        ? gatewayChannel[0].partner_id[0]
                        : gatewayChannel[0]?.partner_id;
                }
            }
            if (!partnerId) return;
            const action = await component.env.services.orm.call(
                "res.partner",
                "initiate_call_on_whatsapp",
                [partnerId]
            );
            if (action && action.type === "ir.actions.act_window") {
                await component.env.services.action.doAction(action);
            }
        },
        sequence: 16,
    });
