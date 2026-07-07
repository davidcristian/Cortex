import { useEffect } from "react";

import { latestReply } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Orb } from "./Orb";
import { Panel } from "./Panel";
import { Preview } from "./Preview";

// The mode router: the panel is always mounted (its `open` class drives the enter/travel
// animation); the orb and preview mount only in their modes. Also owns the global keys. Esc
// dismisses (→ orb mid-stream), Ctrl/Cmd+N starts a new chat, Ctrl+↑/↓ cycle recent chats,
// and Ctrl+K toggles the switcher (ADR-0021).
interface OverlayProps {
  readonly controller: OverlayController;
  readonly dark: boolean;
  readonly onToggleTheme: () => void;
}

export function Overlay({ controller, dark, onToggleTheme }: OverlayProps) {
  const { state, submit, stop, dismiss, open, newChat, openSession, cyclePrev, cycleNext, toggleSwitcher } =
    controller;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.ctrlKey || event.metaKey;
      if (event.key === "Escape") {
        if (state.mode !== "hidden") {
          dismiss();
        }
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
  }, [state.mode, dismiss, newChat, toggleSwitcher, cyclePrev, cycleNext]);

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
        onSelectSession={openSession}
      />
      {state.mode === "orb" ? <Orb onClick={open} /> : null}
      {state.mode === "preview" ? <Preview reply={latestReply(state)} onClick={open} /> : null}
    </>
  );
}
