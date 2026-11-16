/** @odoo-module **/
import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";
import {
    getRemoteAudioElement,
    playRemoteAudio,
    waitForIceComplete,
    prepareSdpForMeta,
} from "@odoo_whatsapp_calling/js/wa_webrtc_utils";
import {startCallRecording} from "@odoo_whatsapp_calling/js/wa_call_recorder";

/**
 * Client action used by the WhatsApp call buttons.
 *
 * The backend returns this action from `initiate_call_on_whatsapp` /
 * `call_on_whatsapp`, so the tab that received the click starts the call
 * directly. Before, the backend published a bus notification and the call
 * only started if that browser had an open websocket: when the bus was
 * disconnected the button silently did nothing.
 */
export const WHATSAPP_CALL_ACTION = "whatsapp_calling.initiate_business_call";

const CALL_LOCK_KEY = "odoo_whatsapp_call_lock";
const CALL_LOCK_DURATION = 7000;

async function initiateBusinessCall(env, payload) {
    if (!payload) {
        return;
    }
    const notificationService = env.services.notification;
    try {
        const now = Date.now();
        if (!sessionStorage.getItem("odoo_tab_id")) {
            sessionStorage.setItem("odoo_tab_id", Math.random().toString(36).substring(2));
        }
        const tabId = sessionStorage.getItem("odoo_tab_id");

        const existingLock = JSON.parse(localStorage.getItem(CALL_LOCK_KEY) || "{}");

        if (
            existingLock.timestamp &&
            now - existingLock.timestamp < CALL_LOCK_DURATION &&
            existingLock.tabId !== tabId
        ) {
            console.log("[WA CALL] Another tab already initiated the call recently, skipping...");
            return;
        }
        localStorage.setItem(
            CALL_LOCK_KEY,
            JSON.stringify({
                tabId,
                timestamp: now,
            })
        );

        await new Promise((r) => setTimeout(r, 200));

        const leader = JSON.parse(localStorage.getItem(CALL_LOCK_KEY) || "{}");
        if (leader.tabId !== tabId) {
            console.log("[WA CALL] Another tab became leader, skipping...");
            return;
        }

        console.log("[WA CALL] This tab is leader, executing Meta API call...");

        const pc = new RTCPeerConnection({
            iceServers: [{urls: "stun:stun.l.google.com:19302"}],
        });

        // Local audio
        let localStream;
        try {
            localStream = await navigator.mediaDevices.getUserMedia({audio: true});
        } catch (err) {
            notificationService.add(
                "Microphone access is required to make WhatsApp calls. Allow the microphone in your browser and try again.",
                {type: "danger", sticky: true}
            );
            throw err;
        }
        localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));

        // Remote audio
        const remoteAudio = getRemoteAudioElement();
        pc.ontrack = (event) => {
            console.log("Remote audio track received", event.streams);
            remoteAudio.srcObject = event.streams[0];
            playRemoteAudio(remoteAudio);
        };

        // Create local offer
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        await waitForIceComplete(pc);
        const localSdp = pc.localDescription?.sdp || offer.sdp;

        // Call backend API
        if (localSdp && offer.type) {
            const response = await rpc("/wa/call/initiate", {
                partner_id: payload.partner_id,
                sdp_offer: {sdp: prepareSdpForMeta(localSdp), type: offer.type},
                provider_id: payload.provider_id,
            });

            if (response && response.error) {
                notificationService.add(response.error || "Unknown error", {
                    type: "danger",
                    sticky: true,
                });
            } else {
                if (!window._wa_calls) window._wa_calls = {};
                if (response.calls?.length) {
                    window._wa_calls[response.calls[0].id] = pc;
                    window._wa_pc = pc;
                    startCallRecording(response.calls[0].id, pc);
                    console.log("Business call started, PC stored:", response.calls[0].id);
                }
            }
        }
    } catch (err) {
        console.error("Failed to handle business_initiated_call:", err);
        notificationService.add(err.message || "Call setup failed", {
            type: "danger",
            sticky: true,
        });
    }
}

registry.category("actions").add(WHATSAPP_CALL_ACTION, (env, action) => {
    // Do not await: the dialog that returned the action can be closed right
    // away, like the old bus based flow did.
    initiateBusinessCall(env, action.params?.payload);
});
