/* @odoo-module */

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { Composer } from "@mail/core/common/composer";
import { _t } from "@web/core/l10n/translation";
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
    OpenWhatsappCall() {
        var self = this
        this.env.services.rpc.call(
            'res.partner', 'whatsapp_call_from_chatter',
            [this.props.threadModel, this.props.threadId]
        ).then(function (result) {
            if (result && result.type) {
                self.env.services.action.doAction(result, {
                    onClose: function () {
                        self.store.Thread.insert({
                            model: self.props.threadModel,
                            id: self.props.threadId,
                        }).fetchNewMessages()
                    }
                });
            }
        });
    },
});
