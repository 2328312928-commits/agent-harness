import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const baseUrl = process.env.HARNESS_WEB_URL ?? "http://127.0.0.1:5173";
const outputDir = resolve(process.cwd(), "../artifacts");

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: edge,
  headless: true,
});

const results = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "New run" }).waitFor();
  await page.getByRole("heading", { name: "Recent runs" }).waitFor();
  const desktopOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  if (desktopOverflow) throw new Error("Desktop layout has horizontal overflow");
  await page.screenshot({
    path: resolve(outputDir, "console-desktop.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Run task" }).click();
  await page.getByText("Trace", { exact: true }).first().waitFor();
  await page.getByText("Plan", { exact: true }).first().waitFor();
  await page.getByText("Checkpoint saved").first().waitFor({ timeout: 15000 });
  const taskLabel = page.locator(".task-header .task-title > span");
  await taskLabel.waitFor();
  const taskText = (await taskLabel.textContent()) ?? "";
  const taskId = taskText.replace("RUN /", "").trim();
  await page.waitForFunction(
    (expectedTaskId) => {
      const heading = document.querySelector(".task-header .task-title > span");
      if (!heading || !heading.textContent?.includes(expectedTaskId)) return false;
      const badge = document.querySelector(".task-header .status-badge");
      const status = badge?.textContent?.trim();
      return status === "Completed" || status === "Partial" || status === "Failed";
    },
    taskId,
    { timeout: 30000 },
  );
  const taskStatus = await page
    .locator(".task-header .status-badge")
    .textContent();
  await page.screenshot({
    path: resolve(outputDir, "console-trace.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "工具" }).click();
  await page.getByRole("heading", { name: "Registered tools" }).waitFor();
  const toolCount = await page.locator(".tool-card").count();
  if (toolCount < 14) throw new Error(`Expected at least 14 tools, got ${toolCount}`);
  await page.screenshot({
    path: resolve(outputDir, "console-tools.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".nav-item").first().click();
  await page.getByRole("heading", { name: "New run" }).waitFor();
  const mobileOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  if (mobileOverflow) throw new Error("Mobile layout has horizontal overflow");
  await page.screenshot({
    path: resolve(outputDir, "console-mobile.png"),
    fullPage: true,
  });

  results.push({
    desktopOverflow,
    mobileOverflow,
    toolCount,
    taskId,
    taskStatus,
    screenshots: [
      "console-desktop.png",
      "console-trace.png",
      "console-tools.png",
      "console-mobile.png",
    ],
  });
} finally {
  await browser.close();
}

console.log(JSON.stringify(results, null, 2));
