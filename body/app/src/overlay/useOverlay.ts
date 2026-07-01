import { useCallback, useEffect, useReducer, useRef } from "react";

import type { BrainBridge, Cancellation } from "../bridge/types";
import { type OverlayState, initialState, isTurnActive, reduce } from "./overlayState";

const PREVIEW_MS = 6000;

/** The overlay controller: the reducer wired to the brain bridge + the preview auto-fade timer. */
export interface OverlayController {
  readonly state: OverlayState;
  submit(text: string): void;
  dismiss(): void;
  open(): void;
  newChat(): void;
}

export function useOverlay(bridge: BrainBridge, sessionId: string): OverlayController {
  const [state, dispatch] = useReducer(reduce, initialState);
  const cancelRef = useRef<Cancellation | null>(null);

  // A completed preview fades on its own after PREVIEW_MS (design/overlay-ux.md §4).
  useEffect(() => {
    if (state.mode !== "preview") {
      return undefined;
    }
    const timer = setTimeout(() => dispatch({ kind: "previewFade" }), PREVIEW_MS);
    return () => clearTimeout(timer);
  }, [state.mode]);

  const submit = useCallback(
    (text: string) => {
      if (text.trim().length === 0 || isTurnActive(state)) {
        return;
      }
      dispatch({ kind: "submit", text });
      cancelRef.current = bridge.converse(sessionId, text.trim(), {
        onEvent: (event) => dispatch({ kind: "event", event }),
        onError: (error) => dispatch({ kind: "transportError", error }),
      });
    },
    [state, bridge, sessionId],
  );

  const dismiss = useCallback(() => dispatch({ kind: "dismiss" }), []);
  const open = useCallback(() => dispatch({ kind: "open" }), []);
  const newChat = useCallback(() => {
    cancelRef.current?.();
    dispatch({ kind: "newChat" });
  }, []);

  return { state, submit, dismiss, open, newChat };
}
