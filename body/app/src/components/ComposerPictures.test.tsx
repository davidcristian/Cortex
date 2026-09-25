import { createEvent, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { describe, expect, it, vi } from "vitest";

import type { Picture } from "../overlay/pictures";
import { Composer } from "./Composer";

const picture = (id: string, width: number): Picture => ({
  id,
  image: { data: new Uint8Array([1]), mimeType: "image/png", width, height: 90 },
  preview: `data:image/png;base64,${id}`,
});

interface StageProps {
  readonly pictures?: readonly Picture[];
  readonly note?: string | null;
  readonly onAttach?: (files: readonly Blob[]) => void;
  readonly onDetach?: (id: string) => void;
}

function Stage({ pictures = [], note = null, onAttach = vi.fn(), onDetach = vi.fn() }: StageProps) {
  const field = useRef<HTMLTextAreaElement>(null!);
  return (
    <Composer
      field={field}
      busy={false}
      draft=""
      arrival={null}
      onSubmit={vi.fn()}
      onDraft={vi.fn()}
      onStop={vi.fn()}
      onResize={vi.fn()}
      pictures={pictures}
      pictureNote={note}
      onAttach={onAttach}
      onDetach={onDetach}
    />
  );
}

const field = () => screen.getByLabelText("Message");
const pill = () => field().parentElement as HTMLDivElement;
const png = () => new File(["x"], "shot.png", { type: "image/png" });

describe("Composer pictures", () => {
  it("shows each waiting picture as a thumbnail named by its place and size", () => {
    render(<Stage pictures={[picture("a", 160), picture("b", 120)]} />);
    const list = screen.getByRole("list", { name: "Attached pictures" });
    expect(list.querySelectorAll("img")).toHaveLength(2);
    expect(screen.getByAltText("Picture 2, 120 by 90").getAttribute("src")).toBe(
      "data:image/png;base64,b",
    );
    expect(pill().classList.contains("stacked")).toBe(true);
  });

  it("shows no list and stays one row with nothing attached", () => {
    render(<Stage />);
    expect(screen.queryByRole("list")).toBeNull();
    expect(pill().classList.contains("stacked")).toBe(false);
  });

  it("removes the picture whose control was pressed", () => {
    const onDetach = vi.fn();
    render(<Stage pictures={[picture("a", 160), picture("b", 120)]} onDetach={onDetach} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove picture 2" }));
    expect(onDetach).toHaveBeenCalledWith("b");
  });

  it("says why a picture was refused as an alert, on its own row", () => {
    render(<Stage note="attachment 2 is bad" />);
    expect(screen.getByRole("alert").textContent).toBe("attachment 2 is bad");
    expect(pill().classList.contains("stacked")).toBe(true);
  });

  it("takes pasted files as pictures and keeps them out of the field", () => {
    const onAttach = vi.fn();
    render(<Stage onAttach={onAttach} />);
    const file = png();
    const paste = createEvent.paste(field(), { clipboardData: { files: [file] } });
    fireEvent(field(), paste);
    expect(onAttach).toHaveBeenCalledWith([file]);
    expect(paste.defaultPrevented).toBe(true);
  });

  it("lets a paste of text through untouched", () => {
    const onAttach = vi.fn();
    render(<Stage onAttach={onAttach} />);
    const paste = createEvent.paste(field(), { clipboardData: { files: [] } });
    fireEvent(field(), paste);
    expect(onAttach).not.toHaveBeenCalled();
    expect(paste.defaultPrevented).toBe(false);
  });

  it("takes dropped files, and claims only a drag that holds files", () => {
    const onAttach = vi.fn();
    render(<Stage onAttach={onAttach} />);
    const withFiles = createEvent.dragOver(pill(), { dataTransfer: { types: ["Files"] } });
    fireEvent(pill(), withFiles);
    expect(withFiles.defaultPrevented).toBe(true);
    const withText = createEvent.dragOver(pill(), { dataTransfer: { types: ["text/plain"] } });
    fireEvent(pill(), withText);
    expect(withText.defaultPrevented).toBe(false);
    const file = png();
    const drop = createEvent.drop(pill(), { dataTransfer: { files: [file] } });
    fireEvent(pill(), drop);
    expect(onAttach).toHaveBeenCalledWith([file]);
    expect(drop.defaultPrevented).toBe(true);
  });

  it("ignores a drop that holds no files", () => {
    const onAttach = vi.fn();
    render(<Stage onAttach={onAttach} />);
    const drop = createEvent.drop(pill(), { dataTransfer: { files: [] } });
    fireEvent(pill(), drop);
    expect(onAttach).not.toHaveBeenCalled();
    expect(drop.defaultPrevented).toBe(false);
  });
});
