import { type Dispatch, useCallback, useEffect, useRef } from "react";

import type { BrainBridge } from "../bridge/types";
import { type Action, type OverlayState, cycleTarget, isTurnActive } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

// The chat catalog (ADR-0021), split from `useOverlay` so the hook that owns a turn is not also
// the hook that owns the list of chats: this one keeps the switcher's list fresh, hydrates a chat
// into the panel, and carries the four user-only catalog writes (open, rename, delete, pin) plus
// cycling. Both halves are callbacks and effects over the same reducer, so nothing but `dispatch`
// and the turn-abandon callback crosses between them. Splitting it also keeps both files under the
// repo line cap.

const SESSION_LIST_LIMIT = 50;

/** The chat-catalog half of `OverlayController`; every member is re-exported from it verbatim. */
export interface SessionCatalog {
  /** Load a stored chat into the panel. `announce` is the caller's answer to whether the swap says
   *  what arrived: false from a switcher row, whose own accessible name is that chat's title, and
   *  true from a control that points at a chat without naming it, which is the reminder card's
   *  open link and the cycle keys below (`overlay/notice.ts`). */
  openSession(sessionId: string, announce: boolean): void;
  renameSession(sessionId: string, title: string): void;
  deleteSession(sessionId: string): void;
  setSessionPinned(sessionId: string, pinned: boolean): void;
  cyclePrev(): void;
  cycleNext(): void;
}

/**
 * Keeps the store-backed chat list current and exposes the operations over it.
 *
 * `abandonTurn` is the caller's "drop whatever is in flight" (deny a pending confirm, then close
 * the event stream): switching or deleting a chat has to run it before the write lands, and it
 * belongs to the turn half, so it is passed in rather than re-implemented here.
 */
export function useSessionCatalog(
  bridge: BrainBridge,
  state: OverlayState,
  dispatch: Dispatch<Action>,
  abandonTurn: () => void,
  newSessionId: () => string,
): SessionCatalog {
  const refreshSessions = useCallback(() => {
    bridge
      .listSessions(SESSION_LIST_LIMIT)
      .then((sessions) => dispatch({ kind: "sessionsLoaded", sessions }))
      .catch(() => {
        // A failed list leaves the current list in place. The switcher just won't update.
      });
  }, [bridge, dispatch]);

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
  }, [latestSessionId, bridge, dispatch]);

  const openSession = useCallback(
    (sessionId: string, announce: boolean) => {
      abandonTurn();
      bridge
        .sessionMessages(sessionId)
        .then((messages) => dispatch({ kind: "openSession", sessionId, messages, announce }))
        .catch(() => {
          // Leave the current chat in place if its history cannot load. Nothing is announced
          // either, the notice riding the same dispatch as the swap it describes, so a history
          // that never arrives cannot have its title read out as though it had.
        });
    },
    [abandonTurn, bridge, dispatch],
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

  // A user-only destructive catalog write (ADR-0021), fired only after the switcher row's own
  // "are you sure" confirm. Deleting the currently-open chat first tears down its in-flight turn and
  // denies any pending confirm, so a still-streaming reply cannot re-materialize the chat with a
  // `store.append` after the delete lands (the current-session hazard). The row is dropped and the
  // list refreshed only on success; a failed delete leaves the chat and list as they are, and the
  // next refresh restores the row. On success, deleting the open chat resets the panel to a fresh
  // chat (reducer), so a deleted transcript is never shown.
  const deleteSession = useCallback(
    (sessionId: string) => {
      if (sessionId === state.sessionId) {
        abandonTurn();
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
    [state.sessionId, abandonTurn, bridge, dispatch, refreshSessions, newSessionId],
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

  // Both cycle keys announce. They are the reason the live region exists: a keystroke names no
  // chat, the swap moves no focus, and the panel's whole contents change under a reader who is
  // told nothing otherwise (`overlay/notice.ts`).
  const cyclePrev = useCallback(() => {
    const target = cycleTarget(state.sessions, state.sessionId, -1);
    if (target !== null) {
      openSession(target, true);
    }
  }, [state.sessions, state.sessionId, openSession]);

  const cycleNext = useCallback(() => {
    const target = cycleTarget(state.sessions, state.sessionId, 1);
    if (target !== null) {
      openSession(target, true);
    }
  }, [state.sessions, state.sessionId, openSession]);

  return { openSession, renameSession, deleteSession, setSessionPinned, cyclePrev, cycleNext };
}
