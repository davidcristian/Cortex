import { type Dispatch, useCallback, useEffect, useRef } from "react";

import type { BrainBridge } from "../bridge/types";
import { type Action, type OverlayState, cycleTarget, isTurnActive } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

// The chat catalog, split from `useOverlay` so the hook that owns a turn is not also the hook that
// owns the list of chats. Both halves are callbacks and effects over the same reducer, so nothing
// but `dispatch` and the turn-abandon callback crosses between them.

const SESSION_LIST_LIMIT = 50;

/** The chat-catalog half of `OverlayController`; every member is re-exported from it verbatim. */
export interface SessionCatalog {
  /** Load a stored chat into the panel. `announce` is false from a switcher row, whose own
   *  accessible name is that chat's title, and true from a control that points at a chat without
   *  naming it, which is the reminder card's open control and the cycle keys. */
  openSession(sessionId: string, announce: boolean): void;
  renameSession(sessionId: string, title: string): void;
  deleteSession(sessionId: string): void;
  setSessionPinned(sessionId: string, pinned: boolean): void;
  cyclePrev(): void;
  cycleNext(): void;
}

/** Keeps the store-backed chat list current and exposes the operations over it. `abandonTurn` is
 *  the caller's "drop whatever is in flight": switching or deleting a chat has to run it before
 *  the write, and it belongs to the turn half, so it is passed in. */
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
        // A failed list leaves the current one in place; the switcher simply does not update.
      });
  }, [bridge, dispatch]);

  // Load the chat list on mount, and refresh it each time a turn finishes: `turnActive` goes false
  // to true to false per turn, so the false edges reload it.
  const turnActive = isTurnActive(state);
  useEffect(() => {
    if (!turnActive) {
      refreshSessions();
    }
  }, [turnActive, refreshSessions]);

  // Refresh it on each summon too. The other two triggers can be very old by the time anyone
  // looks: mount happens once for a tray-resident body, and the last turn may have been days ago.
  useSummonEffect(state.mode !== "hidden", refreshSessions);

  // Cold-start restore: when the first chat list arrives, adopt the top listed chat so a summon
  // reaches it instead of an empty fresh one. One attempt per mount, and whether it applies is the
  // reducer's `touched` guard, so a racing summon, submit, cycle or new chat always wins.
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
        // Leave the fresh chat in place if the history cannot be read.
      });
  }, [latestSessionId, bridge, dispatch]);

  const openSession = useCallback(
    (sessionId: string, announce: boolean) => {
      abandonTurn();
      bridge
        .sessionMessages(sessionId)
        .then((messages) => dispatch({ kind: "openSession", sessionId, messages, announce }))
        .catch(() => {
          // Leave the current chat in place if its history cannot be read. Nothing is announced
          // either, because the notice is sent with the swap it describes.
        });
    },
    [abandonTurn, bridge, dispatch],
  );

  // Relabel the chat, then re-list, because the write does not return the new title.
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

  // Deleting the currently open chat first tears down its turn and denies any pending confirm, so
  // a still-streaming reply cannot recreate the chat after the delete. The row is dropped and the
  // list refreshed only on success.
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

  // Set the chat's `pinned` state, then re-list, because the brain decides the new grouping.
  const setSessionPinned = useCallback(
    (sessionId: string, pinned: boolean) => {
      bridge
        .setSessionPinned(sessionId, pinned)
        .then(refreshSessions)
        .catch(() => {
          // A lost write leaves the list as it is; the switcher keeps its old grouping.
        });
    },
    [bridge, refreshSessions],
  );

  // Both cycle keys announce. They are the reason the live region exists: a keystroke names no
  // chat, the swap moves no focus, and the panel's whole contents change.
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
