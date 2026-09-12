import { chromium } from "playwright-core";
import { mkdir, rename } from "node:fs/promises";
import { resolve } from "node:path";

const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const baseUrl = process.env.HARNESS_WEB_URL ?? "https://agent-harness-console.onrender.com";
const outputDir = resolve(process.cwd(), "../artifacts/video");
const videoDir = resolve(outputDir, "short-parts");

await mkdir(videoDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: edge,
  headless: true,
});

const warmContext = await browser.newContext({ viewport: { width: 1280, height: 720 } });
const warmPage = await warmContext.newPage();
await warmPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 120_000 });
await warmPage.getByRole("heading", { name: "New run" }).waitFor({ timeout: 120_000 });
await warmContext.close();

const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: {
    dir: videoDir,
    size: { width: 1280, height: 720 },
  },
});
const page = await context.newPage();

async function caption(title, text) {
  await page.evaluate(
    ({ title, text }) => {
      let overlay = document.getElementById("agent-harness-caption");
      if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "agent-harness-caption";
        overlay.innerHTML = `
          <style>
            #agent-harness-caption {
              position: fixed;
              z-index: 2147483647;
              left: 24px;
              right: 24px;
              bottom: 20px;
              padding: 11px 15px;
              color: #f6f8fb;
              background: rgba(8, 13, 20, 0.94);
              border-left: 4px solid #e9a23b;
              border-radius: 5px;
              box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
              font-family: "Microsoft YaHei", sans-serif;
              pointer-events: none;
            }
            #agent-harness-caption strong {
              color: #e9a23b;
              font-size: 13px;
              margin-right: 10px;
            }
            #agent-harness-caption span {
              font-size: 18px;
              font-weight: 600;
            }
            #agent-harness-pointer {
              position: fixed;
              z-index: 2147483646;
              width: 18px;
              height: 18px;
              margin: -9px 0 0 -9px;
              border: 3px solid #fff;
              border-radius: 50%;
              background: #e24747;
              box-shadow: 0 0 0 4px rgba(226, 71, 71, 0.28);
              pointer-events: none;
            }
          </style>
          <strong></strong><span></span>
        `;
        document.documentElement.appendChild(overlay);
        const pointer = document.createElement("div");
        pointer.id = "agent-harness-pointer";
        pointer.style.display = "none";
        document.documentElement.appendChild(pointer);
      }
      overlay.querySelector("strong").textContent = title;
      overlay.querySelector("span").textContent = text;
    },
    { title, text },
  );
}

async function movePointer(page, x, y) {
  await page.evaluate(
    ({ x, y }) => {
      const pointer = document.getElementById("agent-harness-pointer");
      if (pointer) {
        pointer.style.display = "block";
        pointer.style.left = `${x}px`;
        pointer.style.top = `${y}px`;
      }
    },
    { x, y },
  );
}

async function click(locator) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("Element is not visible");
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y, { steps: 8 });
  await movePointer(page, x, y);
  await page.waitForTimeout(350);
  await locator.click();
}

async function wait(seconds) {
  await page.waitForTimeout(seconds * 1000);
}

async function waitForCurrentTaskTerminal() {
  const label = page.locator(".task-header .task-title > span");
  await label.waitFor({ timeout: 30_000 });
  const text = (await label.textContent()) ?? "";
  const taskId = text.replace("RUN /", "").trim();
  if (!taskId.startsWith("task_")) {
    throw new Error(`Could not resolve current task id from: ${text}`);
  }
  await page.waitForFunction(
    (expectedTaskId) => {
      const heading = document.querySelector(".task-header .task-title > span");
      if (!heading || !heading.textContent?.includes(expectedTaskId)) return false;
      const badge = document.querySelector(".task-header .status-badge");
      const status = badge?.textContent?.trim();
      return status === "Completed" || status === "Partial" || status === "Failed";
    },
    taskId,
    { timeout: 60_000 },
  );
  return taskId;
}

try {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 120_000 });
  await page.getByRole("heading", { name: "New run" }).waitFor({ timeout: 120_000 });
  await caption("ONLINE DEMO", "运行任务，观察真实 Agent 执行数据");
  await wait(6);

  await click(page.getByRole("button", { name: "Run task" }));
  await caption("CREATE", "提交任务，后端开始 Plan");
  await page.getByText("Plan", { exact: true }).first().waitFor({ timeout: 30_000 });
  await page.getByText("Checkpoint saved").first().waitFor({ timeout: 30_000 });
  await wait(7);

  await caption("ACT → OBSERVE", "模型选择工具，观察结果后继续执行");
  const taskId = await waitForCurrentTaskTerminal();
  const finalStatus = await page
    .locator(".task-header .status-badge")
    .textContent();
  await wait(9);

  await caption(
    `TASK ${taskId.slice(-6)} / ${finalStatus}`,
    "每个阶段写入持久化事件，可恢复、可追踪",
  );
  await page.locator(".timeline").scrollIntoViewIfNeeded();
  await wait(7);

  await click(page.getByRole("button", { name: "工具" }));
  await page.getByRole("heading", { name: "Registered tools" }).waitFor();
  await caption("MCP + TOOLS", "14 个工具经过统一校验、权限和超时控制");
  await wait(10);
  await click(page.locator(".tool-card").nth(10));
  await caption("TOOL CONTRACT", "5 个工具由独立 MCP Server 动态加载");
  await wait(8);

  await click(page.getByRole("button", { name: "评测" }));
  await page.getByRole("heading", { name: "Benchmark" }).waitFor();
  await caption("EVAL", "在线运行评测，查看成功率、延迟和逐任务结果");
  await wait(11);

  await page.goto(
    "https://github.com/2328312928-commits/agent-harness/blob/main/docs/evaluation-status.md",
    { waitUntil: "domcontentloaded", timeout: 120_000 },
  );
  await caption(
    "EVALUATION",
    "严格工具成功校验、答案校验、恢复语义和模型评测边界",
  );
  await wait(10);

  await caption("RESULT", "可运行、可恢复、可观测、可评测");
  await wait(6);
} finally {
  const video = page.video();
  await context.close();
  await browser.close();
  if (video) {
    const source = await video.path();
    await rename(source, resolve(outputDir, "agent-harness-demo-short.webm"));
  }
}

console.log(resolve(outputDir, "agent-harness-demo-short.webm"));
