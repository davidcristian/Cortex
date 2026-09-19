import { type Dispatch, useCallback } from "react";

import type { BrainBridge, DueReminder } from "../bridge/types";
import type { Action, Mode } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

/** Reads the fired-but-undelivered reminders each time the overlay opens, and returns the
 *  dismisser. It runs on the rising edge of visibility rather than on mount, because the body is
 *  resident in the tray and a mount-time read would deliver into a window nobody is looking at. */
export function useReminders(
  bridge: BrainBridge,
  mode: Mode,
  dispatch: Dispatch<Action>,
): (reminder: DueReminder) => void {
  const pull = useCallback(() => {
    bridge
      .listDueReminders()
      .then((reminders) => dispatch({ kind: "remindersLoaded", reminders }))
      .catch(() => {
        // A failed read leaves the previous cards in place: a brief outage must not empty a
        // surface that says something is waiting.
      });
  }, [bridge, dispatch]);
  useSummonEffect(mode !== "hidden", pull);

  // Dismissal is optimistic: the card leaves now and the ack is sent without waiting, so an
  // unreachable brain cannot make the gesture feel stuck. The ack names the fire this card was
  // read for, so a later fire that replaced it is not cleared by dismissing the older card.
  return useCallback(
    ({ reminderId, firedAtUnixMs }: DueReminder) => {
      dispatch({ kind: "reminderDismissed", reminderId });
      bridge.ackReminder(reminderId, firedAtUnixMs).catch(() => {
        // A lost ack leaves the reminder deliverable, and the next open shows it again.
      });
    },
    [bridge, dispatch],
  );
}
