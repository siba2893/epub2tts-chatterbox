import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NamingPreview from "../NamingPreview";
import * as api from "../../api";

describe("NamingPreview", () => {
  it("renders a row per sample chapter and method columns are clickable", async () => {
    vi.spyOn(api, "getNamingPreview").mockResolvedValue({
      rows: [
        { toc: "One", heading: "Heading 1", class: null, fallback: "fallback-1" },
        { toc: "Two", heading: "Heading 2", class: null, fallback: "fallback-2" },
      ],
    });

    render(
      <NamingPreview
        jobId="x"
        meta={{ title: "T", author: "A" }}
        onChosen={() => undefined}
      />
    );

    // Wait for the rows to render
    await waitFor(() => expect(screen.getByText("One")).toBeInTheDocument());
    expect(screen.getByText("Heading 2")).toBeInTheDocument();

    // Method columns are present
    for (const method of ["toc", "heading", "class", "fallback"]) {
      expect(
        screen.getByRole("columnheader", { name: method })
      ).toBeInTheDocument();
    }
  });

  it("changes the continue button to reflect the picked method", async () => {
    vi.spyOn(api, "getNamingPreview").mockResolvedValue({
      rows: [{ toc: "T", heading: "H", class: null, fallback: "f" }],
    });

    render(<NamingPreview jobId="x" meta={null} onChosen={() => undefined} />);

    await waitFor(() => expect(screen.getByText("T")).toBeInTheDocument());

    // Default is toc
    expect(screen.getByRole("button", { name: /continue with toc/i })).toBeInTheDocument();

    // Click the heading column header
    await userEvent.click(screen.getByRole("columnheader", { name: "heading" }));

    expect(
      screen.getByRole("button", { name: /continue with heading/i })
    ).toBeInTheDocument();
  });
});
