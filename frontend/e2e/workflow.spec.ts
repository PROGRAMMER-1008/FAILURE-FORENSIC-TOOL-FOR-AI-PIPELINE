import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("synthetic investigation and narrow layout", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Find where things went wrong." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "+ New investigation" }).click();
  await page.getByRole("button", { name: "Load invented invoice" }).click();
  await page.getByRole("button", { name: "Queue investigation" }).click();
  await expect(
    page.getByText("Execution finished.", { exact: false }),
  ).toBeVisible({ timeout: 20000 });
  await expect(page.locator(".pipeline-lines.wide [data-edge]")).toHaveCount(5);
  await page.getByRole("button", { name: /Classify document/ }).click();
  await expect(
    page.getByRole("heading", { name: "Output: Document classification" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Extract facts/ }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Output: Fact extraction" }),
  ).toBeVisible();
  await page
    .locator(".pipeline-figure")
    .screenshot({ path: "test-results/flowchart-wide.png" });
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: "test-results/investigation-wide.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".pipeline-lines.narrow")).toBeVisible();
  await expect(page.locator(".pipeline-lines.wide")).toBeHidden();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .locator(".pipeline-figure")
    .screenshot({ path: "test-results/flowchart-narrow.png" });
  await page.screenshot({
    path: "test-results/investigation-narrow.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("combobox", { name: /Verdict/ }).selectOption("confirm");
  await page
    .getByRole("checkbox", { name: "Fact extraction", exact: true })
    .check();
  await page.getByRole("button", { name: "Save review" }).click();
  await expect(page.getByRole("status")).toContainText("Review saved");
  await expect(
    page.getByRole("button", { name: "Run with my correction" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Copy facts to edit" }).click();
  const correction = page.getByLabel(/Corrected value 1/);
  await expect(correction).toHaveValue("999 EUR");
  await correction.fill("814 EUR");
  await page.getByRole("button", { name: "Run with my correction" }).click();
  await expect(page.getByText("Replay of", { exact: false })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Original versus replay" }),
  ).toBeVisible({ timeout: 20000 });
  await page.getByRole("link", { name: "Review dataset", exact: true }).click();
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Freeze selected cases" }).click();
  await expect(
    page.getByRole("link", { name: "Export sanitized JSON" }).first(),
  ).toBeVisible();
  await page.getByRole("link", { name: "Experiments", exact: true }).click();
  await page.getByRole("button", { name: "Run synthetic benchmark" }).click();
  await expect(
    page.getByRole("heading", { name: /Fixture report/ }).first(),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: /Fixture report/ }).first(),
  ).toBeVisible();
});
