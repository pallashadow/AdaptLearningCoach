import { test, expect } from "@playwright/test";

test("loads app shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Agentic Learning" })).toBeVisible();
  await expect(page.getByLabel("Backend URL")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start Dialog" })).toBeVisible();
});
