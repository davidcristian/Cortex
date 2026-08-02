import { traceRowRef } from "../overlay/measured";
import type { Message as MessageModel } from "../overlay/overlayState";
import { Thoughts } from "./Thoughts";
import { WhisperBubble } from "./WhisperBubble";

// A chat bubble. A user's line and a loaded reply are plain neutral bubbles; a live assistant
// reply whispers in through `WhisperBubble` (ADR-0037): an accent mist breathes until the first
// token, letters condense on a continuous front the mist glides along, and the bubble's box
// grows at that front's pace. Until then, live tool/status activity renders as slim inline chips
// above it, between bubbles (design/overlay-ux.md §3), gone on completion. A "thinking" status
// reads as deliberation, not action, so its chip bobs (chip-think) rather than carrying the
// steady tool pulse (ADR-0020 state-aware chip). Once a reply that reasoned settles, the live
// chip drops and the accumulated trace stays available as a collapsed "Thoughts" disclosure
// above the bubble (ADR-0020 addendum, `Thoughts.tsx`): the settled counterpart of the chip,
// resting chrome only since the thinking is done. That disclosure owns its own open state, and
// the whisper latches whether it streamed, which is why both are components rather than markup
// here: this one stays a pure function of the message. Errors render as an alert. Colour lives
// only on the working mist and the error tint.
//
// `onGrow` is how the whisper's drain (which outlives the turn's last render) reaches the
// history's tail pin.

export function Message({
  message,
  onGrow,
}: {
  readonly message: MessageModel;
  readonly onGrow: () => void;
}) {
  if (message.error !== null) {
    return (
      <div className="bubble b-ai b-error" role="alert">
        {message.error}
      </div>
    );
  }

  if (message.role === "user") {
    return <div className="bubble b-user">{message.content}</div>;
  }

  return (
    <>
      {/* Both chips carry the ref that publishes their row height for the disclosure below to
          match (overlay/measured.ts): they are the same box, and whichever the turn shows is on
          screen well before the settled trace that has to be as tall as it. */}
      {message.streaming && message.tool !== null ? (
        <span className="chip" ref={traceRowRef}>
          <span className="chip-t">{message.tool}</span>
        </span>
      ) : null}
      {message.streaming && message.status !== null ? (
        <span
          className={`chip${message.statusState === "thinking" ? " chip-think" : ""}`}
          aria-label={message.statusState === "thinking" ? "Thinking" : undefined}
          ref={traceRowRef}
        >
          <span className="chip-t">{message.status}</span>
        </span>
      ) : null}
      {!message.streaming && message.thoughts !== "" ? (
        <Thoughts trace={message.thoughts} />
      ) : null}
      <WhisperBubble message={message} onGrow={onGrow} />
    </>
  );
}
