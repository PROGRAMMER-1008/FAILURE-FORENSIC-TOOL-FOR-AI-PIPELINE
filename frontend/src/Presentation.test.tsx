// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { OutputView } from "./Presentation";

afterEach(cleanup);
it("preserves false, zero and hostile source text in readable output", () => {
  const { container } = render(
    <OutputView
      value={{
        amount: 0,
        paid: false,
        entities: [{ value: "<script>alert(1)</script>" }],
      }}
    />,
  );
  expect(screen.getByText("0")).toBeTruthy();
  expect(screen.getByText("false")).toBeTruthy();
  expect(screen.getByText("<script>alert(1)</script>")).toBeTruthy();
  expect(container.querySelector("script")).toBeNull();
});
it("distinguishes missing output from an empty collection", () => {
  const { rerender } = render(<OutputView value={null} />);
  expect(screen.getByText("No output recorded.")).toBeTruthy();
  rerender(<OutputView value={[]} />);
  expect(screen.getByText("None recorded.")).toBeTruthy();
});
