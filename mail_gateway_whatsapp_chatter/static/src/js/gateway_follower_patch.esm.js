import {GatewayFollower} from "@mail_gateway/components/gateway_follower/gateway_follower.esm";
import {onMounted, useState} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(GatewayFollower.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({templates: [], selectedTemplateId: false, channel: false});
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
        const channels = this.props.follower.gateway_channels;
        if (channels.length === 0 || this.state.channel) return;
        this.state.channel = channels[0].id;
        this.props.composer.thread.gateway_notifications.push(
            this._getMessageData()
        );
        this.props.composer.thread.isGateway = true;
    },
    onChangeTemplate(ev) {
        const templateId = parseInt(ev.target.value, 10);
        this.state.selectedTemplateId = templateId;
        const notifIndex = this.props.composer.thread.gateway_notifications.findIndex(
            (n) => n.gateway_channel_id === this.state.channel
        );
        if (notifIndex !== -1) {
            this.props.composer.thread.gateway_notifications[notifIndex].whatsapp_template_id =
                templateId || false;
        }
        if (!templateId) return;
        const template = this.state.templates.find((t) => t.id === templateId);
        if (template) {
            this.props.composer.text = template.body;
        }
    },
    onChangeGatewayChannel(ev) {
        const prevChannel = this.state.channel;
        this.state.channel = parseInt(ev.target.value, 10);
        if (prevChannel && this.state.channel) {
            const notifIndex = this.props.composer.thread.gateway_notifications.findIndex(
                (n) => n.gateway_channel_id === prevChannel
            );
            if (notifIndex !== -1) {
                this.props.composer.thread.gateway_notifications.splice(notifIndex, 1);
            }
        }
        if (this.state.channel) {
            this.props.composer.thread.gateway_notifications.push(
                this._getMessageData()
            );
            this.props.composer.thread.isGateway = true;
        } else {
            this._clearGatewayNotifications();
        }
    },
    _getMessageData() {
        const data = {
            partner_id: this.props.follower.id,
            channel_type: "gateway",
            gateway_channel_id: this.state.channel,
        };
        if (this.state.selectedTemplateId) {
            data.whatsapp_template_id = this.state.selectedTemplateId;
        }
        return data;
    },
});
