/** @odoo-module **/
import {Component, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

export class SendWhatsappCallButton extends Component {
    static template = "mail_gateway_whatsapp_call.SendWhatsappCallButton";

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.title = _t("Call on WhatsApp");
        this.state = useState({working: false});
    }

    async onClick() {
        if (this.state.working) return;
        this.state.working = true;
        try {
            await this.props.record.save();
            const partnerId = await this.orm.call(
                "res.partner",
                "resolve_whatsapp_call_partner_id",
                [this.props.record.resModel, this.props.record.resId]
            );
            if (!partnerId) {
                this.notification.add(
                    _t("Nenhum parceiro relacionado encontrado para este registro."),
                    {type: "warning", sticky: true}
                );
                return;
            }
            const action = await this.orm.call(
                "res.partner",
                "initiate_call_on_whatsapp",
                [partnerId]
            );
            if (action && action.type === "ir.actions.act_window") {
                this.action.doAction(action);
            }
        } catch (err) {
            this.notification.add(err.data?.message || err.message || this.title, {
                type: "danger",
                sticky: true,
            });
        } finally {
            this.state.working = false;
        }
    }
}
