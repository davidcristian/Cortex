import { useCallback, useEffect, useReducer, useRef } from "react";

import type { BrainBridge, Cancellation } from "../bridge/types";
import {
  type OverlayState,
  createInitialState,
  cycleTarget,
  isTurnActive,
  reduce,
} from "./overlayState";

const PREVIEW_MS = 6000;
const SESSION_LIST_LIMIT = 50;

/** The overlay controller: the reducer wired to the brain bridge + the preview auto-fade timer. */
export interface OverlayController {
  readonly state: OverlayState;
  submit(text: string): void;
  stop(): void;
  dismiss(): void;
  open(): void;
  newChat(): void;
  openSession(sessionId: string): void;
  cyclePrev(): void;
  cycleNext(): void;
  toggleSwitcher(): void;
}

/**
 * Drives the overlay: owns the current chat's `session_id` (minted via `newSessionId`,
 * default `crypto.randomUUID`), the reducer, and the store-backed chat list. The list
 * loads on mount and refreshes whenever a turn finishes (a completed turn is now a
 * listable session); selecting or cycling loads a chat's history over the bridge.
 */
export function useOverlay(
  bridge: BrainBridge,
  newSessionId: () => string = () => crypto.randomUUID(),
): OverlayController {
  const [state, dispatch] = useReducer(reduce, undefined, () =>
    createInitialState(newSessionId()),
  );
  const cancelRef = useRef<Cancellation | null>(null);

  const refreshSessions = useCallback(() => {
    bridge
      .listSessions(SESSION_LIST_LIMIT)
      .then((sessions) => dispatch({ kind: "sessionsLoaded", sessions }))
      .catch(() => {
        // A failed list leaves the current list in place. The switcher just won't update.
      });
  }, [bridge]);

  // A completed preview fades on its own after PREVIEW_MS (design/overlay-ux.md §4).
  useEffect(() => {
    if (state.mode !== "preview") {
      return undefined;
    }
    const timer = setTimeout(() => dispatch({ kind: "previewFade" }), PREVIEW_MS);
    return () => clearTimeout(timer);
  }, [state.mode]);

  // Load the chat list on mount, and refresh it each time a turn finishes: `turnActive`
  // flips false→true→false per turn, so the false edges (mount + completion) reload.
  const turnActive = isTurnActive(state);
  useEffect(() => {
    if (!turnActive) {
      refreshSessions();
    }
  }, [turnActive, refreshSessions]);

  const submit = useCallback(
    (text: string) => {
      if (text.trim().length === 0 || isTurnActive(state)) {
        return;
      }
      dispatch({ kind: "submit", text });
      cancelRef.current = bridge.converse(state.sessionId, text.trim(), {
        onEvent: (event) => dispatch({ kind: "event", event }),
        onError: (error) => dispatch({ kind: "transportError", error }),
      });
    },
    [state, bridge],
  );

  const stop = useCallback(() => {
    cancelRef.current?.();
    dispatch({ kind: "stop" });
  }, []);
  const dismiss = useCallback(() => dispatch({ kind: "dismiss" }), []);
  const open = useCallback(() => dispatch({ kind: "open" }), []);
  const newChat = useCallback(() => {
    cancelRef.current?.();
    dispatch({ kind: "newChat", sessionId: newSessionId() });
  }, [newSessionId]);
  const toggleSwitcher = useCallback(() => dispatch({ kind: "toggleSwitcher" }), []);

  const openSession = useCallback(
    (sessionId: string) => {
      cancelRef.current?.();
      bridge
        .sessionMessages(sessionId)
        .then((messages) => dispatch({ kind: "openSession", sessionId, messages }))
        .catch(() => {
          // Leave the current chat in place if its history cannot load.
        });
    },
    [bridge],
  );

  const cyclePrev = useCallback(() => {
    const target = cycleTarget(state.sessions, state.sessionId, -1);
    if (target !== null) {
      openSession(target);
    }
  }, [state.sessions, state.sessionId, openSession]);

  const cycleNext = useCallback(() => {
    const target = cycleTarget(state.sessions, state.sessionId, 1);
    if (target !== null) {
      openSession(target);
    }
  }, [state.sessions, state.sessionId, openSession]);

  return {
    state,
    submit,
    stop,
    dismiss,
    open,
    newChat,
    openSession,
    cyclePrev,
    cycleNext,
    toggleSwitcher,
  };
}
