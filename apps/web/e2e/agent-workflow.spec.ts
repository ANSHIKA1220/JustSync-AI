import { test, expect } from "@playwright/test";

test("agent edits and approves an AI suggestion", async ({ page }) => {
  const login = await page.request.post("http://127.0.0.1:8000/auth/demo-login", {
    data: { role: "agent" }
  });
  expect(login.ok()).toBeTruthy();
  const auth = await login.json();
  await page.goto("/login");
  await page.evaluate((payload) => {
    localStorage.setItem("journeysync_token", payload.access_token);
    localStorage.setItem("journeysync_user", JSON.stringify(payload.user));
  }, auth);
  await page.goto("/workspace");
  await expect(page.getByText("Agent Workspace")).toBeVisible();
  await page.getByLabel("Editable AI suggestion").fill("I edited this response and will prioritize your replacement.");
  await page.getByRole("button", { name: /approve/i }).click();
  await expect(page.getByText(/recorded in audit/i)).toBeVisible();
  await page.goto("/audit");
  await expect(page.getByText("ai_suggestion_approved").first()).toBeVisible();
});
