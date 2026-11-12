import {Thread} from "@mail/core/common/thread_model";
import {patch} from "@web/core/utils/patch";

const formatWhatsAppNumber = (token) => {
    const digits = String(token || "")
        .replace(/\D/g, "")
        .trim();
    if (!digits) {
        return false;
    }
    if (!digits.startsWith("55")) {
        return digits;
    }
    const rest = digits.slice(2);
    const ddd = rest.slice(0, 2);
    const number = rest.slice(2);
    const formatted =
        number.length > 4 ? `${number.slice(0, -4)}-${number.slice(-4)}` : number;
    return `+55 ${ddd} ${formatted}`;
};

patch(Thread.prototype, {
    get gatewayChannelToken() {
        const token = this.gateway_channel_token;
        const channel = this.parent_channel_id;
        const raw = token || (channel ? channel.gateway_channel_token : false);
        return formatWhatsAppNumber(raw);
    },
});
