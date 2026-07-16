import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { BrainBridge, Cancellation } from "../bridge/types";
import {
  type OverlayState,
  createInitialState,
  cycleTarget,
  isTurnActive,
  reduce,
} from "./overlayState";
import { useLink } from "./useLink";
import { useReminders } from "./useReminders";
import { useSummonEffect } from "./useSummonEffect";

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
  /** Rename a chat from the switcher (ADR-0021): write the label, then re-list to show it. */
  renameSession(sessionId: string, title: string): void;
  /** Delete a chat from the switcher (ADR-0021): fire the destructive write after the row's local
   *  confirm, then drop it and re-list; deleting the open chat falls back to a fresh new chat. */
  deleteSession(sessionId: string): void;
  /** Pin or unpin a chat from the switcher (ADR-0021 pinning addendum): write the target state,
   *  then re-list so the switcher re-groups (a pinned chat lifts above the recency window). */
  setSessionPinned(sessionId: string, pinned: boolean): void;
  cyclePrev(): void;
  cycleNext(): void;
  toggleSwitcher(): void;
  toggleSheet(): void;
  /** Hovering the preview pauses its auto-fade; leaving restarts the full countdown. */
  previewHover(hovering: boolean): void;
  /** Answer the pending approval (ADR-0022); stale/duplicate answers are no-ops. */
  respondConfirm(confirmId: string, approved: boolean): void;
  /** Dismiss a delivered reminder: the card leaves and the ack rides the bridge (ADR-0025). */
  dismissReminder(reminderId: string): void;
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
  const [previewHovered, setPreviewHovered] = useState(false);
  // Reminder pull delivery rides its own hook over the same reducer (ADR-0025), and the
  // connection indicator its own (ADR-0011 addendum); both are effects over `dispatch` only.
  const dismissReminder = useReminders(bridge, state.mode, dispatch);
  useLink(bridge, state.mode, state.link, dispatch);

  const refreshSessions = useCallback(() => {
    bridge
      .listSessions(SESSION_LIST_LIMIT)
      .then((sessions) => dispatch({ kind: "sessionsLoaded", sessions }))
      .catch(() => {
        // A failed list leaves the current list in place. The switcher just won't update.
      });
  }, [bridge]);

  // A completed preview fades on its own after PREVIEW_MS (design/overlay-ux.md §4), unless
  // an approval is pending, the turn is still streaming, or the pointer is over the card: a
  // question waits to be seen, a confirm approved mid-turn keeps the preview up until the turn
  // completes, and hover pauses the countdown (leaving restarts it in full; the card's drain
  // bar remounts in step, Preview). The countdown arms only once all are clear (the reducer's
  // previewFade guard is the same rule).
  const previewActive = isTurnActive(state);
  useEffect(() => {
    if (
      state.mode !== "preview" ||
      state.pendingConfirm !== null ||
      previewActive ||
      previewHovered
    ) {
      return undefined;
    }
    const timer = setTimeout(() => dispatch({ kind: "previewFade" }), PREVIEW_MS);
    return () => clearTimeout(timer);
  }, [state.mode, state.pendingConfirm, previewActive, previewHovered]);

  // Leaving preview mode clears the hover latch, so the next preview always arms its fade.
  useEffect(() => {
    if (state.mode !== "preview") {
      setPreviewHovered(false);
    }
  }, [state.mode]);

  // Load the chat list on mount, and refresh it each time a turn finishes: `turnActive`
  // flips false→true→false per turn, so the false edges (mount + completion) reload.
  const turnActive = isTurnActive(state);
  useEffect(() => {
    if (!turnActive) {
      refreshSessions();
    }
  }, [turnActive, refreshSessions]);

  // Refresh it on each summon too (ADR-0021 refresh deferral). Both other triggers can be
  // arbitrarily old by the time anyone looks: mount happens once for a tray-resident body, and
  // the last turn may have been days ago. This is also how a list that failed to load (the
  // brain was down, and the `.catch` above left the switcher empty) fills in once it is back,
  // which the connection indicator beside it now explains.
  useSummonEffect(state.mode !== "hidden", refreshSessions);

  // Cold-start restore (ADR-0021 refinement): when the first chat list arrives, adopt the top
  // listed chat (`sessions[0]`) so summoning lands on it instead of an empty fresh chat. The list
  // is pinned-first (pinning addendum), so this is the top pinned chat when any is pinned, else the
  // most recent, the same one ordered surface the switcher and cycling read. One attempt per mount
  // (the ref also absorbs StrictMode's double-fired effect,
  // and blocks re-adoption if a later list refresh moves `latestSessionId` while the chat is
  // still untouched); whether it applies is the reducer's `touched` guard, decided at dispatch
  // time, so a racing summon, submit, cycle, or explicit new chat always wins.
  const adoptAttempted = useRef(false);
  const latestSessionId = state.sessions[0]?.sessionId;
  useEffect(() => {
    if (adoptAttempted.current || latestSessionId === undefined) {
      return;
    }
    adoptAttempted.current = true;
    bridge
      .sessionMessages(latestSessionId)
      .then((messages) => dispatch({ kind: "adoptSession", sessionId: latestSessionId, messages }))
      .catch(() => {
        // Leave the fresh chat in place if the history cannot load (the openSession rule).
      });
  }, [latestSessionId, bridge]);

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

  // Dropping the turn's event stream (cancelRef) mutes the JS sink but does not half-close
  // the request stream in the Tauri embedding, so a mid-turn confirm would otherwise sit
  // pending brain-side until its timeout (a zombie turn). Every turn-ending action therefore
  // sends an explicit deny for a still-pending confirm first, resolving it immediately
  // (fail-closed all the same, since the user did not approve). A confirm the brain already
  // resolved is no longer pending, so this sends nothing: the answer the user never gave
  // stays off the wire. ADR-0022.
  const denyPendingConfirm = useCallback(() => {
    const pending = state.pendingConfirm;
    if (pending !== null) {
      bridge.respondConfirm(pending.confirmId, false).catch(() => {
        // Non-fatal. The brain still denies by timeout if the answer is lost.
      });
    }
  }, [state.pendingConfirm, bridge]);

  const stop = useCallback(() => {
    denyPendingConfirm();
    cancelRef.current?.();
    dispatch({ kind: "stop" });
  }, [denyPendingConfirm]);

  const respondConfirm = useCallback(
    (confirmId: string, approved: boolean) => {
      // Only the live question can be answered: a double-click (or StrictMode re-fire) and a
      // stale card race the same guard. The second answer is a no-op (ADR-0022).
      if (state.pendingConfirm?.confirmId !== confirmId) {
        return;
      }
      bridge.respondConfirm(confirmId, approved).catch(() => {
        // A lost answer is non-fatal. The brain denies by timeout (fail-closed).
      });
      dispatch({ kind: "confirmAnswered", approved });
    },
    [state.pendingConfirm, bridge],
  );
  const dismiss = useCallback(() => {
    denyPendingConfirm();
    dispatch({ kind: "dismiss" });
  }, [denyPendingConfirm]);
  const open = useCallback(() => dispatch({ kind: "open" }), []);
  const newChat = useCallback(() => {
    denyPendingConfirm();
    cancelRef.current?.();
    dispatch({ kind: "newChat", sessionId: newSessionId() });
  }, [denyPendingConfirm, newSessionId]);
  const toggleSwitcher = useCallback(() => dispatch({ kind: "toggleSwitcher" }), []);
  const toggleSheet = useCallback(() => dispatch({ kind: "toggleSheet" }), []);
  const previewHover = useCallback((hovering: boolean) => setPreviewHovered(hovering), []);

  const openSession = useCallback(
    (sessionId: string) => {
      denyPendingConfirm();
      cancelRef.current?.();
      bridge
        .sessionMessages(sessionId)
        .then((messages) => dispatch({ kind: "openSession", sessionId, messages }))
        .catch(() => {
          // Leave the current chat in place if its history cannot load.
        });
    },
    [denyPendingConfirm, bridge],
  );

  // A user-only catalog write (ADR-0021): relabel the chat, then re-list so the switcher shows
  // the new title (the write does not return it). A failed rename leaves the list unchanged.
  const renameSession = useCallback(
    (sessionId: string, title: string) => {
      bridge
        .renameSession(sessionId, title)
        .then(refreshSessions)
        .catch(() => {
          // A lost write leaves the list as it is; the switcher simply does not relabel.
        });
    },
    [bridge, refreshSessions],
  );

  // A user-only DESTRUCTIVE catalog write (ADR-0021), fired only after the switcher row's own
  // "are you sure" confirm. Deleting the currently-open chat first tears down its in-flight turn and
  // denies any pending confirm, so a still-streaming reply cannot re-materialize the chat with a
  // `store.append` after the delete lands (the current-session hazard). The row is dropped and the
  // list refreshed only on success; a failed delete leaves the chat and list as they are, and the
  // next refresh restores the row. On success, deleting the open chat resets the panel to a fresh
  // chat (reducer), so a deleted transcript is never shown.
  const deleteSession = useCallback(
    (sessionId: string) => {
      if (sessionId === state.sessionId) {
        denyPendingConfirm();
        cancelRef.current?.();
      }
      bridge
        .deleteSession(sessionId)
        .then(() => {
          dispatch({ kind: "sessionDeleted", sessionId, fallbackSessionId: newSessionId() });
          refreshSessions();
        })
        .catch(() => {
          // A lost delete leaves the chat and the list unchanged; the brain still holds it.
        });
    },
    [state.sessionId, denyPendingConfirm, bridge, refreshSessions, newSessionId],
  );

  // A user-only catalog write (ADR-0021 pinning addendum): set the chat's pin state, then re-list
  // so the switcher re-groups (the brain unions a pinned chat into the listing above the recency
  // window). A failed pin leaves the list unchanged; the switcher simply keeps its old grouping.
  const setSessionPinned = useCallback(
    (sessionId: string, pinned: boolean) => {
      bridge
        .setSessionPinned(sessionId, pinned)
        .then(refreshSessions)
        .catch(() => {
          // A lost write leaves the list as it is; the switcher simply does not re-group.
        });
    },
    [bridge, refreshSessions],
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
    renameSession,
    deleteSession,
    setSessionPinned,
    cyclePrev,
    cycleNext,
    toggleSwitcher,
    toggleSheet,
    previewHover,
    respondConfirm,
    dismissReminder,
  };
}
