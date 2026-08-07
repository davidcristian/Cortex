import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { BrainBridge, Cancellation } from "../bridge/types";
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

/** The overlay controller: the reducer wired to the brain bridge + the preview auto-fade timer.
 *  The chat-catalog half (open, rename, delete, pin, cycle) is `useSessionCatalog`'s and is spread
 *  in verbatim, so a component still sees one flat controller. */
export interface OverlayController extends SessionCatalog {
  readonly state: OverlayState;
  submit(text: string): void;
  /** Park the composer's field under the chat on screen (`overlay/drafts.ts`). The composer is
   *  controlled by that entry, so this is what typing in it does and the only thing it does. */
  setDraft(text: string): void;
  stop(): void;
  dismiss(): void;
  open(): void;
  /** Mint a fresh chat over whatever is on screen. `announce` follows the same rule the chat
   *  catalog's `openSession` follows: Ctrl+N speaks, since a keystroke names nothing, and the
   *  header's pencil does not, being labelled with the name of what arrives (`notice.ts`). */
  newChat(announce: boolean): void;
  /** Open or shut the chat switcher, on the chat: pressed from a tucked panel or from behind the
   *  console the key summons and OPENS, since a reader who cannot see the list has none to shut
   *  (`chromeState.ts`). `announce` follows the same door rule the swap arms follow
   *  (`notice.ts`): Ctrl+K speaks what the list holds, since the key leaves the caret where it was,
   *  and the header's chats button does not, carrying `aria-expanded` under the caret already. */
  toggleSwitcher(announce: boolean): void;
  /** Show a console tab (ADR-0032, ADR-0035). Idempotent, so the tab strip switches with it. */
  openConsole(tab: ConsoleTab): void;
  /** Open or close one console tab from its own opener in the hint strip (or the ? key). */
  toggleConsole(tab: ConsoleTab): void;
  /** Leave the console in one step, whichever tab is up (Esc, the header's chevron). */
  closeConsole(): void;
  /** Hovering the preview pauses its auto-fade; leaving restarts the full countdown. */
  previewHover(hovering: boolean): void;
  /** Answer the pending approval (ADR-0022); stale/duplicate answers are no-ops. */
  respondConfirm(confirmId: string, approved: boolean): void;
  /** Dismiss a delivered reminder: the card leaves and the ack rides the bridge (ADR-0025). */
  dismissReminder(reminderId: string): void;
}

/**
 * Drives the overlay: owns the current chat's `session_id` (minted via `newSessionId`,
 * default `crypto.randomUUID`), the reducer, and the turn in flight. The store-backed chat list
 * and everything that writes to it live in `useSessionCatalog`, over this same reducer.
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

  // "Drop whatever is in flight", in the order that matters: deny first (while the confirm is
  // still known), then close the stream. Everything that ends a turn without answering it does
  // exactly this, the catalog's chat switch and delete included.
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
      cancelRef.current = bridge.converse(state.sessionId, text.trim(), {
        onEvent: (event) => dispatch({ kind: "event", event }),
        onError: (error) => dispatch({ kind: "transportError", error }),
      });
    },
    [state, bridge],
  );

  // Stable, so a keystroke re-renders on the state it changed and nothing else: this is the one
  // callback that fires per character, and rebuilding it would re-render the composer twice over.
  const setDraft = useCallback((text: string) => dispatch({ kind: "draft", text }), []);

  const stop = useCallback(() => {
    abandonTurn();
    dispatch({ kind: "stop" });
  }, [abandonTurn]);

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
