// The dot is kept current by what turns already prove, a probe on each summon and after each turn,
// and a re-check while an unhealthy link is on screen. A poll that always runs spends a request
// per interval with nobody looking.

import { type Dispatch, useCallback, useEffect, useRef } from "react";

import type { BrainBridge } from "../bridge/types";
import type { LinkView } from "./linkState";
import type { Action, Mode } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

/** How long after an unhealthy answer the overlay asks again, while it is on screen. It is the
 *  recovery pace of a supervised local process that restarts in seconds, so it is not a setting. */
export const LINK_RECHECK_MS = 5000;

/** Keeps `state.link` current: probes on each summon and when a turn ends on screen and green,
 *  and while the brain is not ready, again at a fixed pace. Nothing runs while hidden. */
export function useLink(
  bridge: BrainBridge,
  mode: Mode,
  link: LinkView,
  turnActive: boolean,
  dispatch: Dispatch<Action>,
): void {
  const visible = mode !== "hidden";
  // At most one probe is out: a hide-then-summon while the brain hangs would otherwise start a
  // second one behind the first, and two answers could arrive out of order.
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
        // The IPC itself rejected, which says nothing about the brain, so keep the last state.
        dispatch({ kind: "linkProbeEnded" });
      })
      .finally(() => {
        inFlight.current = false;
      });
  }, [bridge, dispatch]);

  useSummonEffect(visible, probe);

  // Every streamed event sets the dot green, so a turn's own events cannot show what the turn left
  // behind, such as a swap back that gave up. A turn that ended unhealthy is already rechecked.
  const unhealthy = link.state !== "ready";
  const wasActive = useRef(turnActive);
  useEffect(() => {
    const ended = wasActive.current && !turnActive;
    wasActive.current = turnActive;
    if (ended && visible && !unhealthy) {
      probe();
    }
  }, [turnActive, visible, unhealthy, probe]);

  // An interval rather than a timer restarted per answer: chaining on the answer would make the
  // loop depend on React observing the in-flight flag flip, and a probe that answers within one
  // batch never renders that flip, which would end the recovery after a single retry.
  useEffect(() => {
    if (!visible || !unhealthy) {
      return undefined;
    }
    const ticker = setInterval(probe, LINK_RECHECK_MS);
    return () => clearInterval(ticker);
  }, [visible, unhealthy, probe]);
}
