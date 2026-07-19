import type { MarkStyle } from "../mark/marks";
import { BubbleMark } from "./BubbleMark";

/** The minimized "thinking" mark: the bubble, warping on its own clock (skipped under reduced
 *  motion, which freezes it into a still pose). Click reopens the in-progress turn. */
export function Orb({ style, onClick }: { readonly style: MarkStyle; readonly onClick: () => void }) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <button className="orb" onClick={onClick} aria-label="Reopen (still working)" type="button">
      <BubbleMark style={style} size={64} idPrefix="orb" animated={!reduced} />
    </button>
  );
}
