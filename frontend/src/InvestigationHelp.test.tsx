// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CorrectionEditor, FindingSummary } from "./InvestigationHelp";
afterEach(cleanup);
it("does not imply correctness from successful execution or missing findings", () => {
  render(<FindingSummary status="succeeded" finding={null} />);
  expect(screen.getByRole("heading").textContent).toContain(
    "not enough evidence",
  );
  expect(screen.getByText(/does not guarantee/)).toBeTruthy();
});
it("edits a fact while retaining the other fields", () => {
  const change = vi.fn();
  render(
    <CorrectionEditor
      value={JSON.stringify({
        entities: [{ name: "Total", value: "999 EUR", entity_type: "amount" }],
        confidence: 5,
      })}
      onChange={change}
    />,
  );
  fireEvent.change(screen.getByLabelText(/Corrected value 1/), {
    target: { value: "814 EUR" },
  });
  const result = JSON.parse(change.mock.calls[0][0]);
  expect(result.confidence).toBe(5);
  expect(result.entities[0]).toEqual({
    name: "Total",
    value: "814 EUR",
    entity_type: "amount",
  });
});
it("handles malformed JSON without losing the editor value", () => {
  render(<CorrectionEditor value="{" onChange={() => {}} />);
  expect(screen.getByRole("alert").textContent).toContain("invalid");
});
