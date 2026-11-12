import {Message} from "@mail/core/common/message";
import {patch} from "@web/core/utils/patch";

patch(Message.prototype, {
    get attClass() {
        const res = super.attClass;
        if (this.message.gateway_type === "whatsapp") {
            res["o_whatsapp_message"] = true;
        }
        return res;
    },
});
