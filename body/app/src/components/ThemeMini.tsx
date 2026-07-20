import { type Theme, resolveTheme } from "../theme/themes";

/** A miniature of the panel wearing one theme: the desktop ground it floats on, the glass panel
 *  itself, and three bars standing in for the title, a reply and the composer.
 *
 *  Every colour is read from the theme's own tokens rather than restated here, which is what makes
 *  the picker plug-and-play with the registry: a theme added to `THEMES` previews itself. That is
 *  also why the bars are the tokens that CARRY the panel's contrast (text, muted, field) instead of
 *  the bubble fills, which are a few percent of alpha and vanish at 3px tall. */
export function ThemeMini({ theme }: { readonly theme: Theme }) {
  const t = theme.tokens;
  return (
    <span className="mini" style={{ background: t.bg }}>
      <span className="mini-panel" style={{ background: t.panel, borderColor: t.stroke }}>
        <span className="mini-title" style={{ background: t.text }} />
        <span className="mini-msg" style={{ background: t.muted }} />
        <span className="mini-pill" style={{ background: t.field, borderColor: t.muted }} />
      </span>
    </span>
  );
}

/** The Auto tile's art: one mini split diagonally between the two themes Auto can land on.
 *
 *  Which two is asked of the resolver rather than named, because "follow the system" resolves to
 *  exactly the default dark and the default light theme; naming them here would be a second copy
 *  of a decision `themes.ts` already owns, and would quietly lie the day those defaults change. */
export function AutoMini() {
  return (
    <span className="mini-split">
      <ThemeMini theme={resolveTheme(null, true)} />
      <span className="mini-half">
        <ThemeMini theme={resolveTheme(null, false)} />
      </span>
    </span>
  );
}
