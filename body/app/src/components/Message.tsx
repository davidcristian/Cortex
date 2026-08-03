import { traceRowRef } from "../overlay/measured";
import type { Message as MessageModel } from "../overlay/overlayState";
import { Thoughts } from "./Thoughts";
import { WhisperBubble } from "./WhisperBubble";

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
