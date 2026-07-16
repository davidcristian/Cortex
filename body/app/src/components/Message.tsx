import type { Message as MessageModel } from "../overlay/overlayState";

// A chat bubble. Neutral at rest; while streaming it carries the accent glow + caret and reveals
// each word fluidly (per-word spans keyed by index, so only new words animate in). Until the
// first token arrives, a thinking shimmer holds the bubble; live tool/status activity renders as
// slim inline chips above it, between bubbles (design/overlay-ux.md §3), gone on completion. A
// "thinking" status reads as deliberation, not action, so its chip bobs (chip-think) rather than
// carrying the steady tool pulse (ADR-0020 state-aware chip). Once a reply that reasoned settles,
// the live chip drops and the accumulated trace stays available as a collapsed "Thoughts"
// disclosure above the bubble (ADR-0020 addendum): the settled counterpart of the chip, resting
// chrome only since the thinking is done. Errors render as an alert. Color lives only in the
// working/error states.
export function Message({ message }: { readonly message: MessageModel }) {
  const tone = message.role === "user" ? "b-user" : "b-ai";

  if (message.error !== null) {
    return (
      <div className={`bubble ${tone} b-error`} role="alert">
        {message.error}
      </div>
    );
  }

  const thinking = message.streaming && message.content === "";
  const words = message.content.split(" ");
  return (
    <>
      {message.streaming && message.tool !== null ? (
        <span className="chip">
          <span className="chip-t">{message.tool}</span>
        </span>
      ) : null}
      {message.streaming && message.status !== null ? (
        <span
          className={`chip${message.statusState === "thinking" ? " chip-think" : ""}`}
          aria-label={message.statusState === "thinking" ? "Thinking" : undefined}
        >
          <span className="chip-t">{message.status}</span>
        </span>
      ) : null}
      {!message.streaming && message.thoughts !== "" ? (
        <details className="thoughts">
          <summary className="thoughts-sum">Thoughts</summary>
          <div className="thoughts-body">{message.thoughts}</div>
        </details>
      ) : null}
      <div className={`bubble ${tone}${message.streaming ? " streaming" : ""}`}>
        {thinking ? (
          <span className="thinking" aria-label="Thinking">
            <i />
            <i />
            <i />
          </span>
        ) : (
          <>
            {words.map((word, index) => (
              // eslint-disable-next-line react/no-array-index-key -- stable append-only stream
              <span key={index} className="w">{`${word} `}</span>
            ))}
            {message.streaming ? <span className="caret" aria-hidden="true" /> : null}
          </>
        )}
      </div>
    </>
  );
}
