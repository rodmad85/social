/* @odoo-module */

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";
import { prettifyMessageContent } from "@mail/utils/common/format";

patch(Chatter.prototype, {
    OpenWhatsappComposer() {
        var self = this
         this.env.services.action.doAction(
            {
                type: 'ir.actions.act_window',
                res_model: 'wa.compose.message',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    active_model: this.props.threadModel,
                    active_id: this.props.threadId,
                },
            },
            { onClose: () => {
                self.store.Thread.insert({model: self.props.threadModel,id: self.props.threadId,}).fetchNewMessages()
              }
            }
        );
    },
});
