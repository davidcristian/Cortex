import { useEffect, useRef } from "react";

/**
 * Run `effect` once per summon, on the rising edge of visibility, re-arming when the overlay
 * hides.
 *
 * The body lives resident in the tray, so "on mount" is the wrong moment for anything the
 * user is meant to see or benefit from: it happens once, days before the window is looked at.
 * The latch gives exactly one run per summon, absorbs StrictMode's double-fired mount effect,
 * and does not re-run when the overlay merely changes shape while staying visible (panel to
 * orb to preview and back), because it never hid.
 *
 * This is the shape the reminder pull established (ADR-0025) and now also the trigger for the
 * connection probe and the chat-list refresh (ADR-0011 / ADR-0021 addenda): the three things
 * the overlay should learn *because someone is looking*, rather than on a timer that runs
 * while nobody is.
 */
export function useSummonEffect(visible: boolean, effect: () => void): void {
  const armed = useRef(false);
  useEffect(() => {
    if (!visible) {
      armed.current = false;
      return;
    }
    if (armed.current) {
      return;
    }
    armed.current = true;
    effect();
  }, [visible, effect]);
}
