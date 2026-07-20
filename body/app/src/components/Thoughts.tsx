import { useId, useState } from "react";

import { Collapse } from "./Collapse";

/** The settled reply's reasoning trace, as a disclosure that rolls open (ADR-0020 addendum). */
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
