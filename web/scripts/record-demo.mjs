import { chromium } from "playwright-core";
import { mkdir, rename } from "node:fs/promises";
import { resolve } from "node:path";

const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const baseUrl = process.env.HARNESS_WEB_URL ?? "http://127.0.0.1:8080";
const outputDir = resolve(process.cwd(), "../artifacts/video");
const videoDir = resolve(outputDir, "parts");
const fast = process.env.SHOWCASE_FAST === "1";
const scale = fast ? 0.05 : 1;

await mkdir(videoDir, { recursive: true });
const browser = await chromium.launch({
  executablePath: edge,
  headless: true,
});
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
              left: 32px;
              right: 32px;
              bottom: 24px;
              padding: 15px 19px 16px;
              color: #f5f8fc;
              background: rgba(8, 13, 20, 0.94);
              border: 1px solid #344154;
              border-left: 4px solid #e9a23b;
              border-radius: 6px;
              box-shadow: 0 10px 34px rgba(0, 0, 0, 0.45);
              font-family: "Microsoft YaHei", sans-serif;
              pointer-events: none;
            }
            #agent-harness-caption .caption-label {
              color: #e9a23b;
              font-size: 13px;
              font-weight: 700;
              margin-bottom: 6px;
              letter-spacing: 0;
            }
            #agent-harness-caption .caption-text {
              font-size: 21px;
              line-height: 1.5;
              font-weight: 600;
              letter-spacing: 0;
            }
          </style>
          <div class="caption-label"></div>
          <div class="caption-text"></div>
        `;
        document.documentElement.appendChild(overlay);
      }
      overlay.querySelector(".caption-label").textContent = title;
      overlay.querySelector(".caption-text").textContent = text;
    },
    { title, text },
  );
}

async function wait(seconds) {
  await page.waitForTimeout(Math.max(250, seconds * 1000 * scale));
}

async function open(url, title, text) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90_000 });
  await wait(1);
  await caption(title, text);
}

try {
  await open(
    "https://github.com/2328312928-commits/agent-harness",
    "Agent Harness",
    "一个可检查点恢复、可观测、可评测的 Agent Runtime，而不是只包一层聊天界面。",
  );
  await wait(16);

  await open(
    "https://github.com/2328312928-commits/agent-harness#architecture",
    "系统架构",
    "Runtime 将 Provider、Tool、MCP、Memory、Context、Sandbox、Checkpoint 和 Eval 拆成可替换组件。",
  );
  await wait(24);

  await open(
    baseUrl,
    "任务运行",
    "控制台展示任务完成率、延迟、Checkpoint 数量和成本，所有数据来自持久化记录。",
  );
  await wait(18);

  await page.getByRole("button", { name: "Run task" }).click();
  await wait(3);
  await caption(
    "Plan → Act → Observe → Reflect",
    "任务被后端真实执行，不是前端动画。模型先规划，再按状态机调用工具并检查结果。",
  );
  await page.getByText("Checkpoint saved").first().waitFor({ timeout: 30_000 });
  await wait(25);

  await caption(
    "实时 Trace 与恢复",
    "模型请求、工具参数、Observation、Reflection、Token、延迟和 Checkpoint 都会写入事件存储。",
  );
  await wait(24);

  await page.getByRole("button", { name: "工具" }).click();
  await page.getByRole("heading", { name: "Registered tools" }).waitFor();
  await caption(
    "MCP 工具注册表",
    "14 个工具契约统一经过 Schema 校验、权限、超时、取消和幂等重试；其中 5 个由独立 MCP Server 动态发现。",
  );
  await wait(28);

  await open(
    "https://github.com/2328312928-commits/agent-harness/blob/main/docs/benchmarks/deepseek-chat-main.md",
    "真实模型评测",
    "DeepSeek Chat 在 100 条稳定任务上全部通过，工具正确率 100%，P95 15.43 秒，总成本约 0.456 美元。",
  );
  await wait(30);

  await open(
    "https://github.com/2328312928-commits/agent-harness/blob/main/docs/failure-cases.md",
    "故障案例",
    "项目记录了 Tool 名称兼容、Tool Call 消息配对、SQLite 并发锁、MCP 超时和恢复上限等真实问题及修复。",
  );
  await wait(27);

  await open(
    "https://github.com/2328312928-commits/agent-harness/releases/tag/v0.1.0",
    "交付物",
    "在线 Demo、Docker Compose、架构图、设计文档、110 条评测集、Release 和可复现 Benchmark 均已发布。",
  );
  await wait(22);

  await caption(
    "结果",
    "这个项目展示的不只是模型调用，而是完整 Agent Runtime 的工程闭环：可运行、可恢复、可观测、可评测。",
  );
  await wait(18);
} finally {
  const video = page.video();
  await context.close();
  await browser.close();
  if (video) {
    const source = await video.path();
    await rename(source, resolve(outputDir, "agent-harness-demo.webm"));
  }
}

console.log(resolve(outputDir, "agent-harness-demo.webm"));

