// Thin wrappers over RTCRtpSender APIs for applying tier parameters and
// handling ICE restart. Isolated here so the session page stays focused on
// lifecycle, and so these are unit-testable.

import type { EncodingParams } from "./encodingTiers";

// Apply encoding params to all video senders on a peer. Safe to call repeatedly —
// setParameters is cheap and idempotent when params match.
export async function applyEncodingParams(
  pc: RTCPeerConnection,
  params: EncodingParams,
): Promise<void> {
  const senders = pc.getSenders();
  for (const sender of senders) {
    const track = sender.track;
    if (!track) continue;

    if (track.kind === "video") {
      // If audio-only, disable video track entirely rather than sending near-zero bitrate.
      track.enabled = !params.audioOnly;
      if (params.audioOnly) continue;

      try {
        const rtcParams = sender.getParameters();
        if (!rtcParams.encodings || rtcParams.encodings.length === 0) {
          rtcParams.encodings = [{}];
        }
        rtcParams.encodings[0].maxBitrate = params.maxBitrate;
        rtcParams.encodings[0].scaleResolutionDownBy = params.scaleResolutionDownBy;
        rtcParams.encodings[0].maxFramerate = params.maxFramerate;
        await sender.setParameters(rtcParams);
      } catch {
        // setParameters can throw on negotiation races — ignore; next poll will retry.
      }
    }
  }
}

// Issue an ICE restart offer. Caller is responsible for forwarding the SDP
// to the remote peer via the signaling channel.
export async function createIceRestartOffer(
  pc: RTCPeerConnection,
): Promise<RTCSessionDescriptionInit | null> {
  try {
    const offer = await pc.createOffer({ iceRestart: true });
    await pc.setLocalDescription(offer);
    return offer;
  } catch {
    return null;
  }
}

export function shouldAttemptIceRestart(state: RTCIceConnectionState): boolean {
  return state === "failed" || state === "disconnected";
}
