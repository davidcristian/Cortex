// Three things keep the connection dot current: every streamed event and every transport failure
// is already a fact about the brain, a probe on each summon, and a re-check while an unhealthy
// link is on screen. A poll that always runs spends a request per interval with nobody looking.

import { type Dispatch, useCallback, useEffect, useRef } from "react";

import type { BrainBridge } from "../bridge/types";
import type { LinkView } from "./linkState";
import type { Action, Mode } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

/** How long after an unhealthy answer the overlay asks again, while it is on screen. It is the
 *  recovery pace of a supervised local process that restarts in seconds, so it is not a setting. */
export const LINK_RECHECK_MS = 5000;

/** Keeps `state.link` current: probes the brain on each summon and, while the overlay is visible
 *  and the brain is not ready, probes again at a fixed pace until it is. Nothing runs while the
 *  overlay is hidden, and nothing runs while a healthy link is on screen. */
export function useLink(
  bridge: BrainBridge,
  mode: Mode,
  link: LinkView,
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

  // An interval rather than a timer restarted per answer: chaining on the answer would make the
  // loop depend on React observing the in-flight flag flip, and a probe that answers within one
  // batch never renders that flip, which would end the recovery after a single retry.
  const unhealthy = link.state !== "ready";
  useEffect(() => {
    if (!visible || !unhealthy) {
      return undefined;
    }
    const ticker = setInterval(probe, LINK_RECHECK_MS);
    return () => clearInterval(ticker);
  }, [visible, unhealthy, probe]);
}
