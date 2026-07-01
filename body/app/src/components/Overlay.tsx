import { useEffect } from "react";

import { latestReply } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Orb } from "./Orb";
import { Panel } from "./Panel";
import { Preview } from "./Preview";

// The mode router: the panel is always mounted (its `open` class drives the enter/travel
// animation); the orb and preview mount only in their modes. Also owns the global keys. Esc
// dismisses (→ orb mid-stream), Ctrl/Cmd+N starts a new chat.
export function Overlay({ controller }: { readonly controller: OverlayController }) {
  const { state, submit, dismiss, open, newChat } = controller;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (state.mode !== "hidden") {
          dismiss();
        }
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
        event.preventDefault();
        newChat();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.mode, dismiss, newChat]);

  return (
    <>
      <Panel
        state={state}
        open={state.mode === "panel"}
        onSubmit={submit}
        onDismiss={dismiss}
        onNewChat={newChat}
      />
      {state.mode === "orb" ? <Orb onClick={open} /> : null}
      {state.mode === "preview" ? <Preview reply={latestReply(state)} onClick={open} /> : null}
    </>
  );
}
