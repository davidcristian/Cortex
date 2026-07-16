import { useEffect, useRef } from "react";

/**
 * Run `effect` once per summon: on the **rising edge of visibility**, re-arming when the
 * overlay hides.
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
