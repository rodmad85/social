import {Chatter} from "@mail/chatter/web_portal/chatter";
import {patch} from "@web/core/utils/patch";
import {onWillStart} from "@odoo/owl";
import {user} from "@web/core/user";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.whatsappActive = false;
        onWillStart(async () => {
            this.isSaleAdmin = await user.hasGroup(
                "sales_team.group_sale_manager"
            );
            this.isSdr = await user.hasGroup(
                "crm_commissions.group_crm_commission_sdr"
            );
        });
    },
    _toggleWhatsappComposer() {
        const willOpen = this.state.composerType !== "gateway";
        this.state.whatsappActive = willOpen;
        this.toggleComposer("gateway");
    },
    toggleComposer(mode = false) {
        super.toggleComposer(mode);
        if (!this.state.composerType) {
            this.state.whatsappActive = false;
        }
    },
    onPostCallback() {
        if (this.props.hasParentReloadOnMessagePosted) {
            this.reloadParentView();
        }
        if (this.state.composerType !== "gateway") {
            this.toggleComposer();
            this.state.whatsappActive = false;
            this.state.jumpThreadPresent++;
        }
        this.load(this.state.thread, this.afterPostRequestList);
    },
});
