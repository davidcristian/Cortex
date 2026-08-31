import { type Theme, resolveTheme } from "../theme/themes";

/** A miniature of the panel drawn in one theme: the desktop ground it sits on, the glass panel
 *  itself, and three bars standing in for the title, a reply and the composer.
 *
 *  Every colour is read from the theme's own tokens rather than restated here, which is what makes
 *  the picker plug-and-play with the registry: a theme added to `THEMES` previews itself. It is
 *  also why the bars use the tokens that carry the panel's contrast (text, muted, field) rather
 *  than the bubble fills, which are a few percent of alpha and disappear at 3px tall. */
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
 *  Which two comes from the resolver rather than being named here, because "follow the system"
 *  resolves to the default dark and the default light theme. Naming them here would be a second
 *  copy of a decision `themes.ts` already holds, and would be wrong the day those defaults
 *  change. */
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
