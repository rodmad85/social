import { Store } from "@mail/core/common/store_service";
import { MessagingMenu } from "@mail/core/public_web/messaging_menu";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(MessagingMenu.prototype, {
    /**
     * Add the WhatsApp tab right after the "All" / "Tudo" (main) tab.
     * Idempotent: does nothing when another module already provides the tab.
     */
    get tabs() {
        const tabs = super.tabs;
        if (tabs.some((tab) => tab.id === "whatsapp")) {
            return tabs;
        }
        const mainIndex = tabs.findIndex((tab) => tab.id === "main");
        tabs.splice(mainIndex + 1, 0, {
            icon: "fa fa-whatsapp",
            id: "whatsapp",
            label: _t("WhatsApp"),
        });
        return tabs;
    },
});

patch(Store.prototype, {
    tabToThreadType(tab) {
        if (tab === "whatsapp") {
            // Gateway conversations (WhatsApp, Telegram, etc.) use channel_type "gateway".
            return ["gateway"];
        }
        return super.tabToThreadType(tab);
    },
});
