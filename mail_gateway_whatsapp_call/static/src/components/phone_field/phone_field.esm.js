/** @odoo-module **/
import {PhoneField} from "@web/views/fields/phone/phone_field";
import {SendWhatsappCallButton} from "../send_whatsapp_call_button/send_whatsapp_call_button.esm";
import {patch} from "@web/core/utils/patch";

patch(PhoneField, {
    components: {
        ...PhoneField.components,
        SendWhatsappCallButton,
    },
    defaultProps: {
        ...PhoneField.defaultProps,
        enableButton: true,
        enableCallButton: true,
    },
    props: {
        ...PhoneField.props,
        enableButton: {type: Boolean, optional: true},
        enableCallButton: {type: Boolean, optional: true},
    },
    extractProps: ({attrs}) => {
        return {
            enableButton: attrs.options.enable_sms,
            enableCallButton: attrs.options.enable_call,
            placeholder: attrs.placeholder,
        };
    },
});
