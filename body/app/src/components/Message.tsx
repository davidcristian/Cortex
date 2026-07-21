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
        <Thoughts trace={message.thoughts} />
      ) : null}
      <WhisperBubble message={message} onGrow={onGrow} />
    </>
  );
}
