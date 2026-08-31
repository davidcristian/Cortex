import { useEffect, useRef } from "react";

/** Run `effect` once per summon, on the rising edge of visibility, and make it ready again when
 *  the overlay hides. The body is resident in the tray, so "on mount" happens once, days before
 *  anyone looks. A change of shape while the overlay stays visible does not re-run it. */
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
