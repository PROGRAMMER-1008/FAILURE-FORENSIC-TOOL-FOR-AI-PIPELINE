import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({
  baseURL: process.env.FF_PUBLIC_BROWSER_URL || "https://127.0.0.1:18444",
  ignoreHTTPSErrors: true,
});

test("public visitors work without a password and cannot share investigation access", async ({ page, context, browser }) => {
  test.skip(!process.env.FF_PUBLIC_BROWSER_URL, "Requires the isolated HTTPS public fixture");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Find where things went wrong." })).toBeVisible();
  await expect(page.getByText("No sign-up needed.", { exact: false })).toBeVisible();
  await expect(page.getByLabel("Workspace password")).toHaveCount(0);
  const cookie = (await context.cookies()).find(c => c.name === "__Host-ff_visitor");
  expect(cookie?.secure && cookie?.httpOnly).toBeTruthy();
  await page.getByRole("link", { name: "+ New investigation" }).click();
  await page.getByRole("button", { name: "Load invented invoice" }).click();
  await page.getByRole("button", { name: "Queue investigation" }).click();
  await expect(page.getByText("Execution finished.", { exact: false })).toBeVisible({ timeout: 20000 });
  const id = page.url().split("#run/")[1];
  const exported = await page.request.get(`/api/v1/runs/${id}/export`);
  expect(exported.status()).toBe(200);
  const other = await browser.newContext({baseURL: process.env.FF_PUBLIC_BROWSER_URL, ignoreHTTPSErrors: true});
  try {
    const otherPage = await other.newPage();
    await otherPage.goto("/");
    await expect(otherPage.getByRole("heading", { name: "No investigations yet." })).toBeVisible();
    expect((await other.request.get(`/api/v1/runs/${id}/export`)).status()).toBe(404);
  } finally { await other.close(); }
  await page.getByRole("link", { name: "Settings & status" }).click();
  await expect(page.getByRole("heading", { name: "No account or API key required" })).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path:"../docs/screenshots/public-visitor.png",fullPage:true});
});
