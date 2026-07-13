import type { Message as MessageModel } from "../overlay/overlayState";

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
