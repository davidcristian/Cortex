import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { SendIcon, StopIcon } from "./icons";

interface ComposerProps {
  readonly busy: boolean;
  /** True while the panel is open; the field takes focus on the rising edge (summon). */
  readonly active: boolean;
  readonly onSubmit: (text: string) => void;
  readonly onStop: () => void;
}

/** The auto-grow ceiling, matching the field's CSS max-height (a few lines, §3). */
const FIELD_MAX_PX = 120;

/** The prompt input: Enter sends, Shift+Enter newlines, and the field grows with its content
 *  up to a few lines. Focus lands here whenever the panel opens (design/overlay-ux.md §7).
 *  While a turn streams the send button becomes a stop that cancels it (§3). */
export function Composer({ busy, active, onSubmit, onStop }: ComposerProps) {
  const [text, setText] = useState("");
  // The composer is always mounted with the panel, so the ref is set before any effect runs.
  const fieldRef = useRef<HTMLTextAreaElement>(null!);

  useEffect(() => {
    if (active) {
      fieldRef.current.focus();
    }
  }, [active]);

  // Auto-grow: collapse, then follow the content's scroll height up to the ceiling; past it
  // the field scrolls internally (the CSS max-height is the same bound).
  useEffect(() => {
    const field = fieldRef.current;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, FIELD_MAX_PX)}px`;
  }, [text]);

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
        ref={fieldRef}
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
