import { type KeyboardEvent, useState } from "react";

interface ComposerProps {
  readonly busy: boolean;
  readonly onSubmit: (text: string) => void;
}

/** The prompt input: Enter sends, Shift+Enter newlines; disabled from sending while streaming. */
export function Composer({ busy, onSubmit }: ComposerProps) {
  const [text, setText] = useState("");

  const submit = () => {
    if (busy) {
      return;
    }
    onSubmit(text);
    setText("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const live = text.trim().length > 0 && !busy;

  return (
    <div className="composer">
      <textarea
        className="field"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask anything…"
        aria-label="Message"
        rows={1}
      />
      <button
        className={`send${live ? " live" : ""}`}
        onClick={submit}
        aria-label={busy ? "Streaming" : "Send"}
        type="button"
      >
        <span className="send-glyph">{busy ? "…" : "↑"}</span>
      </button>
    </div>
  );
}
