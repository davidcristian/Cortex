import type { ConsoleTab } from "../overlay/overlayState";
import { DownArrowKey, ReturnKey, SlidersIcon, UpArrowKey } from "./icons";

interface HintStripProps {
  /** Open (or close again) one console tab: each opener here owns its own tab. */
  readonly onToggleConsole: (tab: ConsoleTab) => void;
}

/** The row of keyboard affordances under the composer, plus the two doors into the console. */
export function HintStrip({ onToggleConsole }: HintStripProps) {
  return (
    <div className="hints">
      <span>
        <b className="key">
          <ReturnKey />
        </b>{" "}
        send
      </span>
      <span>
        <b>Shift</b>
        <b className="key">
          <ReturnKey />
        </b>{" "}
        new line
      </span>
      <span>
        <b>Ctrl</b>
        <b>N</b> new
      </span>
      <span>
        <b>Ctrl</b>
        <b className="key">
          <UpArrowKey />
        </b>
        <b className="key">
          <DownArrowKey />
        </b>{" "}
        chats
      </span>
      <button
        className="qbtn"
        onClick={() => onToggleConsole("appearance")}
        aria-label="Settings"
        type="button"
      >
        <b className="key">
          <SlidersIcon />
        </b>
      </button>
      <button
        className="qbtn"
        onClick={() => onToggleConsole("shortcuts")}
        aria-label="Shortcuts"
        type="button"
      >
        <b>?</b>
      </button>
    </div>
  );
}
