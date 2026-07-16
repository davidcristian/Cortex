import { type Dispatch, useCallback } from "react";

import type { BrainBridge } from "../bridge/types";
import type { Action, Mode } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

// The reminder pull loop (ADR-0025), split from `useOverlay` so the delivery path is its own
// responsibility: that hook owns a turn and the chat list, this owns what fired while nobody
// was looking. Both halves are effects over the same reducer, so nothing but `dispatch`
// crosses between them.

/**
 * Pulls fired-but-undelivered reminders each time the overlay opens and returns the dismisser.
 *
 * The fetch is latched on the rising edge of visibility, not on mount (`useSummonEffect`): the
 * body lives resident in the tray, so a mount-time read would deliver into a window nobody is
 * looking at and the ack-on-dismiss contract would describe a card that was never seen. The
 * latch re-arms on hide, giving exactly one read per summon, and absorbs StrictMode's
 * double-fired mount effect. Re-opening the panel from the orb mid-turn does not refetch, since
 * the overlay never hid.
 */
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

  // Dismissal is optimistic: the card leaves now and the ack rides the bridge unawaited, so an
  // unreachable brain cannot make the gesture feel stuck. A lost ack leaves the reminder
  // deliverable, and the next open surfaces it again, which is the recovery the transport's
  // deliberately unretried `ack_reminder` leans on (a repeated reminder beats a lost one).
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
