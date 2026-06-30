/** @odoo-module */

import { Failure } from "@mail/core/common/failure_model";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Failure.prototype, {
    get body() {
        if (this.notifications?.[0]?.gateway_type === "whatsapp") {
            if (this.notifications.length === 1 && this.lastMessage?.thread) {
                return _t(
                    "An error occurred when sending a WhatsApp message on “%(record_name)s”",
                    { record_name: this.lastMessage.thread.name }
                );
            }
            return _t("An error occurred when sending a WhatsApp message");
        }
        return super.body;
    },
    get modelName() {
        if (this.notifications?.[0]?.gateway_type === "whatsapp") {
            return _t("WhatsApp");
        }
        return super.modelName;
    },
});
