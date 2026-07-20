import { type Dispatch, useCallback, useEffect, useRef } from "react";

import type { BrainBridge } from "../bridge/types";
import { type Action, type OverlayState, cycleTarget, isTurnActive } from "./overlayState";
import { useSummonEffect } from "./useSummonEffect";

const SESSION_LIST_LIMIT = 50;

/** The chat-catalog half of `OverlayController`; every member is re-exported from it verbatim. */
export interface SessionCatalog {
  openSession(sessionId: string): void;
  renameSession(sessionId: string, title: string): void;
  deleteSession(sessionId: string): void;
  setSessionPinned(sessionId: string, pinned: boolean): void;
  cyclePrev(): void;
  cycleNext(): void;
}

/** Keeps the store-backed chat list current and exposes the operations over it. */
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

  useSummonEffect(state.mode !== "hidden", refreshSessions);

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
    (sessionId: string) => {
      abandonTurn();
      bridge
        .sessionMessages(sessionId)
        .then((messages) => dispatch({ kind: "openSession", sessionId, messages }))
        .catch(() => {
          // Leave the current chat in place if its history cannot load.
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

  return { openSession, renameSession, deleteSession, setSessionPinned, cyclePrev, cycleNext };
}
