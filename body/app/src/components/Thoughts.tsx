import { useId, useState } from "react";

import { Collapse } from "./Collapse";

/**
 * The settled reply's reasoning trace, as a disclosure that rolls open (ADR-0020 addendum).
 *
 * This was a `<details>`/`<summary>` pair and could not stay one: neither element can animate the
 * content it reveals, so the whole trace appeared in a single frame and the panel around it then
 * eased for 300ms to catch up, which is the two-motion glitch `Collapse` already fixes for the chat
 * switcher and the reminder stack. The disclosure is rebuilt from parts that do animate: a button
 * carrying `aria-expanded`, and the body inside a `Collapse` that rolls its own height. Reusing
 * that component also brings the `data-morphing` contract with it, so the panel follows the roll
 * frame by frame and the trace unfolding and the window growing to hold it are one movement
 * (`overlay/morph.ts`).
 *
 * `aria-controls` is set only while the body it names exists. `Collapse` keeps the body mounted
 * while the trace is open plus the moment its exit takes, so an attribute left set while the trace
 * is shut would point at an id that is not in the document. Nothing is lost by dropping it, since
 * `aria-expanded` on the button states the disclosure's state and the button is always present.
 *
 * The trace is model output, so it is rendered as one plain text node and nothing else. No markup is
 * parsed and no URL is linkified, here or anywhere else the overlay renders text (ADR-0020).
 */
export function Thoughts({ trace }: { readonly trace: string }) {
  const [open, setOpen] = useState(false);
  // The body carries no label of its own, so the control names it rather than the other way round.
  // A generated id keeps two replies' traces from claiming the same one.
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
