import { useId, useState } from "react";

import { Collapse } from "./Collapse";

/**
 * The settled reply's reasoning trace, as a disclosure that rolls open (ADR-0020 addendum).
 *
 * This was a `<details>`/`<summary>` pair and could not stay one: neither element can animate the
 * content it reveals, so the whole trace appeared in a single frame and the panel around it then
 * eased for 300ms to catch up. Two motions, in the wrong order, which is exactly the glitch
 * `Collapse` already exists to fix for the chat switcher and the reminder stack. So the disclosure
 * is rebuilt out of the parts that do animate: a real button carrying `aria-expanded`, and the body
 * inside a `Collapse` that rolls its own height. Reusing that component rather than writing a second
 * mechanism is the point; it also brings the `data-morphing` contract with it, so the panel follows
 * the roll frame by frame and the trace unfolding and the window growing to hold it read as one
 * movement (`overlay/morph.ts`).
 *
 * `aria-controls` comes and goes with the body it names. `Collapse` keeps the body mounted only
 * while the trace is open, plus the moment it takes to animate the exit, so an attribute left set
 * while the trace is shut would point at an id that is not in the document. A dangling reference is
 * worth nothing to a screen reader and is a thing to go wrong later, and none of the announcement
 * rides on it: `aria-expanded` on the button is what states the disclosure's state, and unlike the
 * body it is always there to be read.
 *
 * The trace is model output, so it is rendered as one plain text node and nothing else. No markup is
 * parsed and no URL is linkified, here or anywhere else the overlay renders text (ADR-0020).
 */
export function Thoughts({ trace }: { readonly trace: string }) {
  const [open, setOpen] = useState(false);
  // The body is unlabelled on its own, so the control has to name it rather than the other way
  // round; a generated id keeps two replies' traces from claiming the same one.
  const bodyId = useId();
  return (
    <div className="thoughts">
      <button
        className="thoughts-sum"
        type="button"
        aria-expanded={open}
        aria-controls={open ? bodyId : undefined}
        onClick={() => setOpen((was) => !was)}
      >
        Thoughts
      </button>
      <Collapse open={open}>
        <div className="thoughts-body" id={bodyId}>
          {trace}
        </div>
      </Collapse>
    </div>
  );
}
