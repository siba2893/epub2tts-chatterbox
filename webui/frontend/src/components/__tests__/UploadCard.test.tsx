import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import UploadCard from "../UploadCard";
import * as api from "../../api";

describe("UploadCard", () => {
  it("renders the styled file picker button and step header", () => {
    render(<UploadCard onUploaded={() => undefined} />);
    expect(screen.getByRole("button", { name: /choose .epub file/i })).toBeInTheDocument();
    expect(screen.getByText(/step 01/i)).toBeInTheDocument();
  });

  it("uploads selected file and calls onUploaded with the response", async () => {
    const spy = vi.spyOn(api, "uploadEpub").mockResolvedValue({
      job_id: "abc123",
      title: "Test Book",
      author: "T. Author",
      chapter_count: 4,
    });
    const onUploaded = vi.fn();

    render(<UploadCard onUploaded={onUploaded} />);

    const file = new File([new Uint8Array([1, 2, 3])], "book.epub", {
      type: "application/epub+zip",
    });
    // The hidden <input type="file"> is the only file input in the component.
    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    await userEvent.upload(input, file);

    expect(spy).toHaveBeenCalledWith(file);
    expect(onUploaded).toHaveBeenCalledWith("abc123", {
      title: "Test Book",
      author: "T. Author",
    });
  });

  it("surfaces backend errors inline without throwing", async () => {
    vi.spyOn(api, "uploadEpub").mockRejectedValue(new Error("boom"));

    render(<UploadCard onUploaded={() => undefined} />);
    const input = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File([new Uint8Array([0])], "x.epub");
    await userEvent.upload(input, file);

    expect(await screen.findByText(/boom/i)).toBeInTheDocument();
  });
});
