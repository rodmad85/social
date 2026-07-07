import {Composer} from "@mail/core/common/composer";
import {patch} from "@web/core/utils/patch";

patch(Composer.prototype, {
    get isSendButtonDisabled() {
        const isSendButtonDisabled = super.isSendButtonDisabled;
        if (this.props.type !== "gateway") {
            return isSendButtonDisabled;
        }
        if (!this.thread?.has_whatsapp_conversation) {
            return (
                isSendButtonDisabled ||
                !this.thread?.gateway_notifications?.every(
                    (n) => n.whatsapp_template_id
                )
            );
        }
        return isSendButtonDisabled;
    },
});
