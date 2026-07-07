import { type KeyboardEvent, useState } from "react";

import { SendIcon, StopIcon } from "./icons";

interface ComposerProps {
  readonly busy: boolean;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
}

/** The prompt input: Enter sends, Shift+Enter newlines. While a turn streams the send button
 *  becomes a stop that cancels it (design/overlay-ux.md §3). */
export function Composer({ busy, onSubmit, onStop }: ComposerProps) {
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
        className={`send${live ? " live" : ""}${busy ? " stopping" : ""}`}
        onClick={busy ? onStop : submit}
        aria-label={busy ? "Stop" : "Send"}
        type="button"
      >
        <span className="send-glyph">{busy ? <StopIcon /> : <SendIcon />}</span>
      </button>
    </div>
  );
}
