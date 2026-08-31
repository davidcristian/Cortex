import { useId, useState } from "react";

import { Collapse } from "./Collapse";

/** The settled reply's reasoning trace, as a disclosure that rolls open. It is a button plus a
 *  `Collapse` rather than `<details>`, which cannot animate what it reveals. The trace is model
 *  output, so it renders as one plain text node: no markup is parsed and no URL becomes a link. */
export function Thoughts({ trace }: { readonly trace: string }) {
  const [open, setOpen] = useState(false);
  // `aria-controls` is set only while the body it names is in the document, and a generated id
  // keeps two replies' traces from claiming the same one.
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
