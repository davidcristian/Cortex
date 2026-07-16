import { type Dispatch, useCallback, useEffect, useRef } from "react";

import type { BrainBridge } from "../bridge/types";
import type { LinkView } from "./linkState";
import type { Action, Mode } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

// The connection indicator's effect half (ADR-0011 addendum). Three things keep the dot honest,
// and none of them is a timer that runs forever:
//
// 1. **The turn keeps it fresh for free.** Every streamed event and every transport failure is
//    already a fact about the seam, folded into the link by the reducer. While anything is
//    happening, the indicator costs nothing and cannot be stale.
// 2. **A probe on each summon.** The dot is only visible when the overlay is, so the moment it
//    becomes visible is the moment its truth matters. One probe per summon, latched exactly
//    like the reminder pull.
// 3. **A recovery re-check while it is on screen and not ready.** Only then. A red dot that can
//    never go green until the user dismisses and re-summons is a worse lie than no dot, and
//    watching for recovery is the one thing neither of the above can do (nothing is streaming,
//    and the overlay is already open). It stops the instant the brain answers ready.
//
// A liveness poll (probe every N seconds, always) was rejected: it spends a request per interval
// forever, most of them while the overlay is hidden and nobody can see the result, and it is
// still stale between ticks, which is exactly the window that (1) covers for free.

/**
 * How long after an unhealthy answer the overlay asks again, while it is on screen. Not a
 * configuration knob: it is the recovery cadence of a supervised local process that restarts in
 * seconds, and nothing outside this file has a reason to hold an opinion about it. The wait is
 * also not the whole gap, since the probe underneath it is itself patient (the resilient
 * transport retries `health` with backoff before answering `down`, ADR-0024).
 */
export const LINK_RECHECK_MS = 5000;

/**
 * Keeps `state.link` current: probes the seam on each summon and, while the overlay is visible
 * and the brain is not ready, re-probes on a fixed cadence until it is. Nothing runs while the
 * overlay is hidden, and nothing runs while a healthy link is on screen.
 */
export function useLink(
  bridge: BrainBridge,
  mode: Mode,
  link: LinkView,
  dispatch: Dispatch<Action>,
): void {
  const visible = mode !== "hidden";
  // At most one probe is outstanding: a hide-then-summon while the brain hangs would otherwise
  // start a second one behind the first, and two answers racing could land out of order.
  const inFlight = useRef(false);

  const probe = useCallback(() => {
    if (inFlight.current) {
      return;
    }
    inFlight.current = true;
    dispatch({ kind: "linkProbing" });
    bridge
      .checkLink()
      .then((status) => dispatch({ kind: "linkObserved", status }))
      .catch(() => {
        // The IPC itself rejected, which says nothing about the brain (the command answers a
        // state even when the brain is down). Keep the last known state, drop the in-flight flag.
        dispatch({ kind: "linkProbeEnded" });
      })
      .finally(() => {
        inFlight.current = false;
      });
  }, [bridge, dispatch]);

  useSummonEffect(visible, probe);

  // The recovery cadence, armed only while an unhealthy link is on screen. It is an interval
  // rather than a timer re-armed per answer, deliberately: chaining on the answer would make
  // the loop depend on React observing the in-flight flag flip, and a probe that answers
  // within one batch never renders that flip, which would silently end the recovery after a
  // single retry. The in-flight guard above is what keeps a slow probe from overlapping a tick.
  const unhealthy = link.state !== "ready";
  useEffect(() => {
    if (!visible || !unhealthy) {
      return undefined;
    }
    const ticker = setInterval(probe, LINK_RECHECK_MS);
    return () => clearInterval(ticker);
  }, [visible, unhealthy, probe]);
}
