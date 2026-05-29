import {GatewayFollower} from "@mail_gateway/components/gateway_follower/gateway_follower.esm";
import {onMounted, useState} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(GatewayFollower.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({templates: []});
        this.orm = useService("orm");
        onMounted(async () => {
            await this._loadTemplates();
            this._autoSelectWhatsapp();
        });
    },
    async _loadTemplates() {
        const templates = await this.orm.searchRead(
            "mail.whatsapp.template",
            [],
            ["id", "name", "body"]
        );
        this.state.templates = templates;
    },
    _autoSelectWhatsapp() {
        const whatsappChannel = this.props.follower.gateway_channels.find(
            (channel) => channel.gateway?.type === "whatsapp"
        );
        if (whatsappChannel && !this.channel) {
            this.channel = whatsappChannel.id;
            this.props.composer.thread.gateway_notifications.push(
                this._getMessageData()
            );
            this.props.composer.thread.isGateway = true;
        }
    },
    onChangeTemplate(ev) {
        const templateId = parseInt(ev.target.value, 10);
        if (!templateId) return;
        const template = this.state.templates.find((t) => t.id === templateId);
        if (template) {
            this.props.composer.text = template.body;
        }
    },
});
