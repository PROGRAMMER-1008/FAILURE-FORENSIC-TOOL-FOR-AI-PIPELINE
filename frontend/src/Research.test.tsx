// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Dataset } from "./Research";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("review dataset boundaries", () => {
  it("renders hostile review text as text and disables demo mutations", async () => {
    const hostile = "<img src=x onerror=alert(1)>";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => ({
        ok: true,
        json: async () =>
          input.endsWith("/versions")
            ? []
            : [
                {
                  id: "case-1",
                  family: "family-1",
                  split: "feedback",
                  payload: { notes: hostile },
                },
              ],
      })),
    );
    const { container } = render(<Dataset readonly={true} />);
    expect(await screen.findByText(/case-1/)).toBeTruthy();
    expect(container.querySelector("img")).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Freeze selected cases",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(container.textContent).toContain(hostile);
  });
  it("surfaces failed requests without pretending the dataset loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        json: async () => ({ error: "not_authorized" }),
      })),
    );
    render(<Dataset readonly={false} />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "not_authorized",
    );
  });
});
