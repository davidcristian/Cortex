import { useState } from "react";

import { MARKS, type MarkStyle } from "../mark/marks";
import { BubbleMark } from "./BubbleMark";

interface MarkPickerProps {
  readonly style: MarkStyle;
  readonly animated: boolean;
  readonly onPick: (name: string) => void;
}

/** The empty state's mark doubles as its own picker (design/overlay-ux.md §4). Clicking it opens
 *  the bubble styles, each drawn live at a glanceable size, and choosing one applies it to both
 *  places the mark appears (here and the orb) at once. The control lives on the mark itself rather
 *  than in the header, so resting chrome gains no color and no fifth button. */
export function MarkPicker({ style, animated, onPick }: MarkPickerProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        className="markbtn"
        type="button"
        aria-expanded={open}
        aria-label={`Mark: ${style.label}. Choose another`}
        onClick={() => setOpen(!open)}
      >
        <BubbleMark style={style} size={54} idPrefix="empty" animated={animated} />
      </button>
      {open ? (
        <div className="markmenu" role="radiogroup" aria-label="Mark style">
          {MARKS.map((choice) => (
            <button
              key={choice.name}
              className={`markopt${choice.name === style.name ? " on" : ""}`}
              type="button"
              role="radio"
              aria-checked={choice.name === style.name}
              title={choice.note}
              onClick={() => {
                onPick(choice.name);
                setOpen(false);
              }}
            >
              <BubbleMark
                style={choice}
                size={34}
                idPrefix={`pick-${choice.name}`}
                animated={animated}
              />
              <span>{choice.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </>
  );
}
