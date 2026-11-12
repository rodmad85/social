import { registry } from "@web/core/registry";

export const mailChatterReloadService = {
    dependencies: ["bus_service", "mail.store"],
    start(env, services) {
        const bus_service = services.bus_service;
        const store = services["mail.store"];
        bus_service.subscribe("mail.record/insert", (payload) => {
            const messages = payload["mail.message"];
            if (!messages || !messages.length) {
                return;
            }
            for (const msgData of messages) {
                if (msgData.model === "discuss.channel" || !msgData.model || !msgData.res_id) {
                    continue;
                }
                const thread = store.Thread.get({ model: msgData.model, id: msgData.res_id });
                if (thread) {
                    thread.fetchNewMessages();
                }
            }
        });
    },
};

registry.category("services").add("mail.chatter.reload", mailChatterReloadService);
