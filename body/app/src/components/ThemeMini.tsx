import { type Theme, resolveTheme } from "../theme/themes";

/** A miniature of the panel drawn in one theme: the desktop ground, the glass panel, and three
 *  bars for the title, a reply and the composer. Every colour is read from the theme's own tokens,
 *  so a theme added to `THEMES` previews itself. */
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

/** The Auto tile's art: one mini split diagonally between the two themes Auto can resolve to.
 *  Which two comes from the resolver rather than being named here, so it stays right when the
 *  defaults change. */
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
