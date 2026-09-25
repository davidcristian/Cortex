import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { BrainBridge, Cancellation, DueReminder } from "../bridge/types";
import {
  type ConsoleTab,
  type OverlayState,
  createInitialState,
  isTurnActive,
  reduce,
} from "./overlayState";
import { useLink } from "./useLink";
import { useReminders } from "./useReminders";
import { type SessionCatalog, useSessionCatalog } from "./useSessionCatalog";

const PREVIEW_MS = 6000;

/** The overlay controller: the reducer wired to the brain bridge plus the preview auto-fade timer.
 *  The chat-catalog half is `useSessionCatalog`'s and is spread in as it is, so a component still
 *  sees one flat controller. */
export interface OverlayController extends SessionCatalog {
  readonly state: OverlayState;
  submit(text: string): void;
  /** Park the composer's field under the chat on screen. The composer is controlled by that
   *  entry, so this is what typing in it does and the only thing it does. */
  setDraft(text: string): void;
  stop(): void;
  dismiss(): void;
  open(): void;
  /** Start a fresh chat over whatever is on screen. `announce` is true for Ctrl+N, which names
   *  nothing, and false for the header's pencil, which is labelled with what arrives. */
  newChat(announce: boolean): void;
  /** Open or shut the chat switcher, on the chat: pressed from a tucked panel or from behind the
   *  console the key summons and opens, since a reader who cannot see the list has none to shut
   *  (`chromeState.ts`). */
  toggleSwitcher(announce: boolean): void;
  /** Show a console tab. Idempotent, so the tab strip switches with it. */
  openConsole(tab: ConsoleTab): void;
  /** Open or close one console tab from its own opener in the hint strip (or the ? key). */
  toggleConsole(tab: ConsoleTab): void;
  /** Leave the console in one step, whichever tab is up (Esc, the header's chevron). */
  closeConsole(): void;
  /** Hovering the preview pauses its auto-fade; leaving restarts the full countdown. */
  previewHover(hovering: boolean): void;
  /** Answer the pending approval; a stale or repeated answer does nothing. */
  respondConfirm(confirmId: string, approved: boolean): void;
  /** Dismiss a delivered reminder: the card leaves and the ack is sent over the bridge. */
  dismissReminder(reminder: DueReminder): void;
}

/** Drives the overlay: owns the current chat's `session_id` (made by `newSessionId`, which
 *  defaults to `crypto.randomUUID`), the reducer, and the turn in flight. The store-backed chat
 *  list and everything that writes to it live in `useSessionCatalog`, over this same reducer. */
export function useOverlay(
  bridge: BrainBridge,
  newSessionId: () => string = () => crypto.randomUUID(),
): OverlayController {
  const [state, dispatch] = useReducer(reduce, undefined, () =>
    createInitialState(newSessionId()),
  );
  const cancelRef = useRef<Cancellation | null>(null);
  const [previewHovered, setPreviewHovered] = useState(false);
  const dismissReminder = useReminders(bridge, state.mode, dispatch);
  useLink(bridge, state.mode, state.link, isTurnActive(state), dispatch);

  // A completed preview fades on its own after PREVIEW_MS, unless an approval is pending, the turn
  // is still streaming, or the pointer is over the card. Leaving the card restarts the countdown in
  // full, and the card's drain bar remounts with it.
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

  // Leaving preview mode clears the hover latch, so the next preview always starts its fade.
  useEffect(() => {
    if (state.mode !== "preview") {
      setPreviewHovered(false);
    }
  }, [state.mode]);

  // Dropping the turn's event stream mutes the sink but does not half-close the request stream in
  // the Tauri embedding, so a mid-turn confirm would sit pending brain-side until its timeout.
  // Every turn-ending action therefore denies a still-pending confirm first.
  const denyPendingConfirm = useCallback(() => {
    const pending = state.pendingConfirm;
    if (pending !== null) {
      bridge.respondConfirm(pending.confirmId, false).catch(() => {
        // Not fatal: the brain still denies by timeout if the answer is lost.
      });
    }
  }, [state.pendingConfirm, bridge]);

  // "Drop whatever is in flight", in the order that matters: deny first, while the confirm is
  // still known, then close the stream.
  const abandonTurn = useCallback(() => {
    denyPendingConfirm();
    cancelRef.current?.();
  }, [denyPendingConfirm]);

  const catalog = useSessionCatalog(bridge, state, dispatch, abandonTurn, newSessionId);

  const submit = useCallback(
    (text: string) => {
      if (text.trim().length === 0 || isTurnActive(state)) {
        return;
      }
      dispatch({ kind: "submit", text });
      cancelRef.current = bridge.converse(state.sessionId, text.trim(), [], {
        onEvent: (event) => dispatch({ kind: "event", event }),
        onError: (error) => dispatch({ kind: "transportError", error }),
      });
    },
    [state, bridge],
  );

  // Stable, so a keystroke re-renders on the state it changed and nothing else: this is the one
  // callback that runs per character.
  const setDraft = useCallback((text: string) => dispatch({ kind: "draft", text }), []);

  const stop = useCallback(() => {
    abandonTurn();
    dispatch({ kind: "stop" });
  }, [abandonTurn]);

  const respondConfirm = useCallback(
    (confirmId: string, approved: boolean) => {
      // Only the live question can be answered, so a double-click and a stale card both stop here.
      if (state.pendingConfirm?.confirmId !== confirmId) {
        return;
      }
      bridge.respondConfirm(confirmId, approved).catch(() => {
        // A lost answer is not fatal: the brain denies by timeout.
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
  const newChat = useCallback(
    (announce: boolean) => {
      abandonTurn();
      dispatch({ kind: "newChat", sessionId: newSessionId(), announce });
    },
    [abandonTurn, newSessionId],
  );
  const toggleSwitcher = useCallback(
    (announce: boolean) => dispatch({ kind: "toggleSwitcher", announce }),
    [],
  );
  const openConsole = useCallback((tab: ConsoleTab) => dispatch({ kind: "openConsole", tab }), []);
  const toggleConsole = useCallback(
    (tab: ConsoleTab) => dispatch({ kind: "toggleConsole", tab }),
    [],
  );
  const closeConsole = useCallback(() => dispatch({ kind: "closeConsole" }), []);
  const previewHover = useCallback((hovering: boolean) => setPreviewHovered(hovering), []);

  return {
    ...catalog,
    state,
    submit,
    setDraft,
    stop,
    dismiss,
    open,
    newChat,
    toggleSwitcher,
    openConsole,
    toggleConsole,
    closeConsole,
    previewHover,
    respondConfirm,
    dismissReminder,
  };
}
