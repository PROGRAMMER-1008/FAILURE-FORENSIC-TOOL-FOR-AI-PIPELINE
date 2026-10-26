import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.use({
  baseURL: process.env.FF_HOSTED_BROWSER_URL || "https://127.0.0.1:18443",
  ignoreHTTPSErrors: true, // Disposable CI certificate only; production uses Render TLS.
});

test("hosted workspace signs in over TLS and revokes logout", async ({ page, context }) => {
  test.skip(!process.env.FF_HOSTED_BROWSER_URL, "Requires the isolated HTTPS hosted fixture");
  await page.goto("/");
  await expect(page.getByRole("heading", {name:"Sign in to your workspace"})).toBeVisible();
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
  await page.getByLabel("Workspace password").fill("test-only-hosted-browser-password");
  await page.getByRole("button", {name:"Sign in",exact:true}).click();
  await expect(page.getByRole("heading", {name:"Find where things went wrong."})).toBeVisible();
  const cookies = await context.cookies();
  const session = cookies.find(cookie => cookie.name === "__Host-ff_session");
  expect(session?.secure).toBeTruthy();
  expect(session?.httpOnly).toBeTruthy();
  await page.getByRole("link", {name:"+ New investigation"}).click();
  await page.getByRole("button", {name:"Load invented invoice"}).click();
  await page.getByRole("button", {name:"Queue investigation"}).click();
  await expect(page.getByText("Execution finished.", {exact:false})).toBeVisible({timeout:20000});
  await page.getByRole("link", {name:"Sign out",exact:true}).click();
  await page.getByRole("button", {name:"Sign out",exact:true}).click();
  await expect(page.getByRole("heading", {name:"Sign in to your workspace"})).toBeVisible();
  await context.addCookies(cookies);
  const response = await page.request.get("/api/v1/runs");
  expect(response.status()).toBe(401);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:"../docs/screenshots/hosted-login.png",fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
