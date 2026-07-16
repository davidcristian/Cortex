import { type Dispatch, useCallback } from "react";

import type { BrainBridge } from "../bridge/types";
import type { Action, Mode } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

/** Pulls fired-but-undelivered reminders each time the overlay opens and returns the dismisser. */
export function useReminders(
  bridge: BrainBridge,
  mode: Mode,
  dispatch: Dispatch<Action>,
): (reminderId: string) => void {
  const pull = useCallback(() => {
    bridge
      .listDueReminders()
      .then((reminders) => dispatch({ kind: "remindersLoaded", reminders }))
      .catch(() => {
        // A failed pull leaves the previous cards in place (the chat list's rule): a transient
        // outage must not silently empty a surface that says something is waiting. The
        // resilient transport has already retried this read with backoff (ADR-0024).
      });
  }, [bridge, dispatch]);
  useSummonEffect(mode !== "hidden", pull);

  return useCallback(
    (reminderId: string) => {
      dispatch({ kind: "reminderDismissed", reminderId });
      bridge.ackReminder(reminderId).catch(() => {
        // Non-fatal, by the rule above.
      });
    },
    [bridge, dispatch],
  );
}
