import {Chatter} from "@mail/chatter/web_portal/chatter";
import {patch} from "@web/core/utils/patch";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.whatsappActive = false;
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
