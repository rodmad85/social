import {Message} from "@mail/core/common/message_model";
import {patch} from "@web/core/utils/patch";

patch(Message.prototype, {
    get whatsappDeliveryIcon() {
        if (this.gateway_type !== "whatsapp" || !this.isSelfAuthored) {
            return "";
        }
        if (this.isPending) {
            return "";
        }
        if (this.whatsapp_notification_status) {
            switch (this.whatsapp_notification_status) {
                case "sent":
                    return "fa fa-check-double";
                case "bounce":
                case "exception":
                    return "fa fa-exclamation-circle";
            }
        }
        if (this.hasSomeoneSeen) {
            return "fa fa-check-double";
        }
        return "fa fa-check";
    },
    get whatsappDeliveryColor() {
        if (this.gateway_type !== "whatsapp" || !this.isSelfAuthored) {
            return "";
        }
        if (this.isPending) {
            return "";
        }
        if (this.hasSomeoneSeen) {
            return "o_whatsapp_delivery_seen";
        }
        if (this.whatsapp_notification_status) {
            switch (this.whatsapp_notification_status) {
                case "bounce":
                case "exception":
                    return "text-danger";
            }
        }
        return "text-muted";
    },
    get whatsappDeliveryHTML() {
        if (this.gateway_type !== "whatsapp" || !this.isSelfAuthored) {
            return "";
        }
        if (this.isPending) {
            return "";
        }
        const icon = this.whatsappDeliveryIcon;
        const color = this.whatsappDeliveryColor;
        if (!icon) {
            return "";
        }
        const cls = icon + (color ? " " + color : "");
        return '<i class="' + cls + '"></i>';
    },
});
