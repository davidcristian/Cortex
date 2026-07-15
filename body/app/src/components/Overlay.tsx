import { useEffect } from "react";

import { latestReply } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Orb } from "./Orb";
import { Panel } from "./Panel";
import { Preview } from "./Preview";

// The mode router: the panel is always mounted (its `open` class drives the enter/travel
// animation); the orb and preview mount only in their modes. Also owns the global keys. Esc
// closes the shortcut sheet if open, else dismisses (→ orb mid-stream); Ctrl/Cmd+N starts a
// new chat, Ctrl+↑/↓ cycle recent chats, Ctrl+K toggles the switcher (ADR-0021), and ?
// (outside the composer, where it is just typing) toggles the shortcut sheet.
interface OverlayProps {
  readonly controller: OverlayController;
  readonly dark: boolean;
  readonly onToggleTheme: () => void;
}

export function Overlay({ controller, dark, onToggleTheme }: OverlayProps) {
  const {
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
    toggleSheet,
    previewHover,
    respondConfirm,
    dismissReminder,
  } = controller;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.ctrlKey || event.metaKey;
      if (event.key === "Escape") {
        if (state.sheetOpen) {
          toggleSheet();
        } else if (state.mode !== "hidden") {
          dismiss();
        }
      } else if (event.key === "?" && !(event.target instanceof HTMLTextAreaElement)) {
        event.preventDefault();
        toggleSheet();
      } else if (mod && event.key.toLowerCase() === "n") {
        event.preventDefault();
        newChat();
      } else if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggleSwitcher();
      } else if (mod && event.key === "ArrowUp") {
        event.preventDefault();
        cyclePrev();
      } else if (mod && event.key === "ArrowDown") {
        event.preventDefault();
        cycleNext();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.mode, state.sheetOpen, dismiss, newChat, toggleSwitcher, toggleSheet, cyclePrev, cycleNext]);

  return (
    <>
      <Panel
        state={state}
        open={state.mode === "panel"}
        dark={dark}
        onToggleTheme={onToggleTheme}
        onSubmit={submit}
        onStop={stop}
        onDismiss={dismiss}
        onNewChat={newChat}
        onToggleSwitcher={toggleSwitcher}
        onToggleSheet={toggleSheet}
        onSelectSession={openSession}
        onRespondConfirm={respondConfirm}
        onDismissReminder={dismissReminder}
      />
      {state.mode === "orb" ? <Orb onClick={open} /> : null}
      {state.mode === "preview" ? (
        <Preview reply={latestReply(state)} onClick={open} onHover={previewHover} />
      ) : null}
    </>
  );
}
