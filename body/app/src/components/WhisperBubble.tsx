import { useRef } from "react";

import type { Message as MessageModel } from "../overlay/overlayState";
import { confirmedOf, letterCountOf, tokenize } from "../whisper/front";
import { useWhisperClock } from "../whisper/useWhisperClock";

// The assistant bubble that streams its reply in letter by letter. A message already settled when
// this instance mounts renders as one plain text node instead. The letter boxes are `aria-hidden`
// behind a hidden copy of the text, so a screen reader reads a reply, not one-letter spans.

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

/** The streaming (or once-streamed) bubble: letters, mist, and the clock that drives both. It is
 *  a separate component so that the plain-history path above runs none of these hooks. */
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
