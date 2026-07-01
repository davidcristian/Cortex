interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
}

/** The completed-while-minimized preview card: shows the reply, click to open, fades on its own. */
export function Preview({ reply, onClick }: PreviewProps) {
  return (
    <button className="preview" onClick={onClick} type="button">
      <div className="pv-t">
        <span className="dot" aria-hidden="true" /> Reply ready
      </div>
      <div className="pv-b">{reply}</div>
      <div className="pv-h">Click to open · fades on its own</div>
      <div className="bar" aria-hidden="true" />
    </button>
  );
}
