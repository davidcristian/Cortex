import type { ReactNode } from "react";

// The header's outline icon set (design/overlay-ux.md §3) is one vocabulary with the theme
// toggle: 1.7px round-cap strokes on a 24 grid, `currentColor`, hollow. Kept tiny and static
// so the buttons stay presentational; state and behavior live in the reducer/hook.
function Icon({ children }: { readonly children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

/** Recent chats (the switcher): two overlapping speech bubbles for "your conversations". */
export function ChatsIcon() {
  return (
    <Icon>
      <path d="M21 13.5l-2.6 -2.5h-6.4a1 1 0 0 1 -1 -1v-4.5a1 1 0 0 1 1 -1h8a1 1 0 0 1 1 1z" />
      <path d="M13 14.5v1.5a1 1 0 0 1 -1 1h-6l-2.6 2.5v-8.5a1 1 0 0 1 1 -1h2" />
    </Icon>
  );
}

/** New chat: a pencil for "compose a new one". */
export function PencilIcon() {
  return (
    <Icon>
      <path d="M4 20h4l10.5 -10.5a2.83 2.83 0 0 0 -4 -4l-10.5 10.5v4" />
      <path d="M13.5 6.5l4 4" />
    </Icon>
  );
}

/** Dismiss: a downward chevron for "tuck it away" (the chat is saved; re-summon restores it). */
export function TuckIcon() {
  return (
    <Icon>
      <path d="M7 10l5 5l5 -5" />
    </Icon>
  );
}
