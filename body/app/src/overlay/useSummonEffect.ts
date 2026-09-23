import { useEffect, useRef } from "react";

/** Run `effect` once per summon, on the rising edge of visibility, and make it ready again when
 *  the overlay hides. The body is resident in the tray, so "on mount" happens once, days before
 *  anyone looks. A change of shape while the overlay stays visible does not re-run it. */
export function useSummonEffect(visible: boolean, effect: () => void): void {
  const fired = useRef(false);
  useEffect(() => {
    if (!visible) {
      fired.current = false;
      return;
    }
    if (fired.current) {
      return;
    }
    fired.current = true;
    effect();
  }, [visible, effect]);
}
