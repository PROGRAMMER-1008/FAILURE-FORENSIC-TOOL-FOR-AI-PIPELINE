// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PipelineGraph } from "./PipelineGraph";
afterEach(cleanup);
it("draws only recorded dependencies and supports selecting a step", () => {
  const select = vi.fn();
  const { container } = render(
    <PipelineGraph
      steps={[
        { id: "extract", dependencies: ["document"] },
        { id: "classify", dependencies: ["document"] },
        { id: "summarize", dependencies: ["extract", "classify", "document"] },
      ]}
      attempts={[]}
      selected="extract"
      onSelect={select}
      origins={["extract"]}
    />,
  );
  expect(container.querySelectorAll(".wide [data-edge]").length).toBe(5);
  expect(container.querySelector('[data-edge="extract-classify"]')).toBeNull();
  expect(
    screen
      .getByRole("button", { name: /SUSPECTED ORIGIN Extract facts pending/ })
      .getAttribute("aria-pressed"),
  ).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: /Classify document/ }));
  expect(select).toHaveBeenCalledWith("classify");
});
it("does not invent an edge absent from the stored graph", () => {
  const { container } = render(
    <PipelineGraph
      steps={[{ id: "summarize", dependencies: ["document"] }]}
      attempts={[]}
      selected="summarize"
      onSelect={() => {}}
    />,
  );
  expect(container.querySelectorAll(".wide [data-edge]").length).toBe(1);
  expect(container.querySelector('[data-edge="extract-summarize"]')).toBeNull();
});
