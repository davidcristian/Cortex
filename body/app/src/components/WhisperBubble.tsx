import { useRef } from "react";

import type { Message as MessageModel } from "../overlay/overlayState";
import { confirmedOf, letterCountOf, tokenize } from "../whisper/front";
import { useWhisperClock } from "../whisper/useWhisperClock";

// The assistant bubble that whispers its reply in (ADR-0037). Which machinery a message gets is
// LATCHED at mount: a message already settled when this instance mounts is history and renders
// as one plain text node with none of it, while a message that was streaming keeps its letter
// DOM after settling, so nothing re-wraps or re-kerns under the reader mid-conversation. That
// latch is presentation state this component owns (the way the Thoughts disclosure owns its open
// state); the reducer only ever appends to `content`.
//
// The letter DOM is presentation, not the accessible text: the word boxes are aria-hidden behind
// a visually hidden copy of the content, so assistive tech reads a reply rather than hundreds of
// one-letter spans, and hears "Thinking" while the bubble is still only breath.

export function WhisperBubble({
  message,
  onGrow,
}: {
  readonly message: MessageModel;
  readonly onGrow: () => void;
}) {
  const live = useRef(message.streaming);
  if (!live.current) {
    return <div className="bubble b-ai">{message.content}</div>;
  }
  return <LiveWhisper message={message} onGrow={onGrow} />;
}

/** The streaming (or once-streamed) bubble: letters, mist, and the clock that drives both. Its
 *  own component so the plain-history path above pays for none of these hooks. */
function LiveWhisper({
  message,
  onGrow,
}: {
  readonly message: MessageModel;
  readonly onGrow: () => void;
}) {
  const bubble = useRef<HTMLDivElement>(null);
  const text = useRef<HTMLSpanElement>(null);
  const mist = useRef<HTMLSpanElement>(null);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const tokens = tokenize(message.content);
  const phase = useWhisperClock(
    { bubble, text, mist },
    {
      streaming: message.streaming,
      letters: letterCountOf(tokens),
      confirmed: confirmedOf(tokens),
      animated: !reduced,
      onGrow,
    },
  );
  return (
    <div ref={bubble} className={`bubble b-ai whisper w-${phase}`}>
      <span className="wtxt" ref={text} aria-hidden="true">
        {tokens.map((token, at) =>
          token.kind === "gap" ? (
            // eslint-disable-next-line react/no-array-index-key -- append-only stream
            <span key={at}>{token.text}</span>
          ) : (
            // eslint-disable-next-line react/no-array-index-key -- append-only stream
            <span key={at} className="wd">
              {[...token.text].map((letter, i) => (
                // eslint-disable-next-line react/no-array-index-key -- letters never reorder
                <span key={i} className="ch">
                  {letter}
                </span>
              ))}
            </span>
          ),
        )}
      </span>
      <span className="sr-copy">{message.content === "" ? "Thinking" : message.content}</span>
      <span className="mist" ref={mist} aria-hidden="true">
        <i />
      </span>
    </div>
  );
}
