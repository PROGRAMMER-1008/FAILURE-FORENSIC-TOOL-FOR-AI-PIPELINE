import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("missing Groq key gives actionable setup without a browser key field", async ({
  page,
}) => {
  await page.route("**/api/v1/config", async (route) => {
    const response = await route.fetch();
    const config = await response.json();
    await route.fulfill({
      json: {
        ...config,
        provider: "groq",
        ai_ready: false,
        credential_status: "missing",
      },
    });
  });
  await page.goto("/#settings");
  await expect(
    page.getByRole("heading", { name: "Groq setup in three steps" }),
  ).toBeVisible();
  await expect(
    page.getByText("Missing — add your key and restart", { exact: true }),
  ).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page
    .getByRole("link", { name: "New investigation", exact: true })
    .click();
  await page.getByRole("button", { name: "Load invented invoice" }).click();
  await expect(
    page.getByRole("button", { name: "Queue investigation" }),
  ).toBeDisabled();
  await expect(page.getByRole("checkbox")).not.toBeChecked();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
