from __future__ import annotations

import json
from pathlib import Path


def task(
    task_id: str,
    category: str,
    difficulty: str,
    goal: str,
    *,
    required_tools: list[str] | None = None,
    answer_contains: list[str] | None = None,
    min_observations: int = 0,
    min_recoveries: int = 0,
    fixture: dict | None = None,
    tags: list[str] | None = None,
) -> dict:
    return {
        "id": task_id,
        "category": category,
        "difficulty": difficulty,
        "goal": goal,
        "expected": {
            "status": "completed",
            "required_tools": required_tools or [],
            "answer_contains": answer_contains or [],
            "min_observations": min_observations,
            "min_recoveries": min_recoveries,
        },
        "max_steps": 12,
        "tags": tags or [],
        "fixture": fixture or {},
    }


def build_tasks() -> list[dict]:
    tasks: list[dict] = []
    difficulties = [
        "easy",
        "easy",
        "easy",
        "medium",
        "medium",
        "medium",
        "hard",
        "medium",
        "easy",
        "medium",
    ]

    reasoning_topics = [
        "幂等操作",
        "指数退避",
        "最终一致性",
        "可观测性的三大支柱",
        "熔断器",
        "检查点",
        "租约机制",
        "背压",
        "蓝绿部署与灰度发布",
        "幂等键",
    ]
    for index, topic in enumerate(reasoning_topics, start=1):
        tasks.append(
            task(
                f"reasoning-{index:03d}",
                "reasoning",
                difficulties[index - 1],
                f"请解释{topic}，并给出一个 Agent Runtime 中的适用场景。不要调用外部工具。",
                tags=["no-tool", "concept"],
            )
        )

    for index in range(1, 11):
        tasks.append(
            task(
                f"filesystem-read-{index:03d}",
                "filesystem_read",
                difficulties[index - 1],
                f"请读取 examples/demo.txt，并确认文件内容是否能够被访问。这是第 {index} 次回归。",
                required_tools=["filesystem.read_file"],
                answer_contains=["Agent Harness demo workspace"],
                min_observations=1,
                tags=["offline", "filesystem", "read"],
            )
        )

    for index in range(1, 11):
        tasks.append(
            task(
                f"filesystem-list-{index:03d}",
                "filesystem_list",
                difficulties[index - 1],
                f"请列出目录 . 下的文件列表，用于第 {index} 次工作区检查。",
                required_tools=["filesystem.list"],
                min_observations=1,
                tags=["offline", "filesystem", "list"],
            )
        )

    arithmetic = [
        (12, 7, "+"),
        (19, 8, "-"),
        (6, 7, "*"),
        (84, 7, "/"),
        (17, 6, "+"),
        (31, 12, "-"),
        (9, 8, "*"),
        (91, 7, "/"),
        (23, 19, "+"),
        (40, 17, "-"),
    ]
    for index, (left, right, operator) in enumerate(arithmetic, start=1):
        answer = {
            "+": left + right,
            "-": left - right,
            "*": left * right,
            "/": left / right,
        }[operator]
        answer_text = str(int(answer)) if float(answer).is_integer() else str(answer)
        tasks.append(
            task(
                f"coding-{index:03d}",
                "coding",
                difficulties[index - 1],
                f"请使用 Python 计算 {left} {operator} {right}，返回计算结果。",
                required_tools=["sandbox.run_python"],
                answer_contains=[answer_text],
                min_observations=1,
                tags=["offline", "sandbox", "calculation"],
            )
        )

    for index in range(1, 11):
        tasks.append(
            task(
                f"database-{index:03d}",
                "database",
                difficulties[index - 1],
                f"请通过 SQL 数据库健康检查确认连接可用，这是第 {index} 个数据库任务。",
                required_tools=["database.query"],
                answer_contains=["healthy"],
                min_observations=1,
                tags=["offline", "database", "readonly"],
            )
        )

    memories = [
        "用户偏好中文回答",
        "项目默认使用 Docker 沙箱",
        "评测优先关注 P95 延迟",
        "工具失败必须进入反思阶段",
        "检查点需要持久化到数据库",
        "长任务需要 Token 预算上限",
        "外部网络工具必须校验 URL",
        "生产环境禁止本地代码执行",
        "长时间记忆需要控制访问频率",
        "评测结果必须保留可追溯 Trace",
    ]
    for index, memory in enumerate(memories, start=1):
        tasks.append(
            task(
                f"memory-{index:03d}",
                "memory",
                difficulties[index - 1],
                f"请记住：{memory}。这是长期记忆写入测试 {index}。",
                required_tools=["memory.remember"],
                min_observations=1,
                tags=["offline", "memory"],
            )
        )

    for index in range(1, 11):
        tasks.append(
            task(
                f"recovery-permission-{index:03d}",
                "recovery",
                "hard",
                f"请读取 examples/demo.txt；权限恢复测试编号 {index}。",
                required_tools=[],
                min_recoveries=1,
                fixture={"tool_permissions": []},
                tags=["offline", "recovery", "permission"],
            )
        )

    for index in range(1, 11):
        tasks.append(
            task(
                f"context-compaction-{index:03d}",
                "context",
                "hard",
                f"总结大量历史约束并给出一句结论，上下文压缩回归 {index}。不要调用外部工具。",
                fixture={"long_context": True},
                tags=["offline", "context", "compaction"],
            )
        )

    browser_urls = [
        "https://example.com",
        "https://example.org",
        "https://www.iana.org/help/example-domains",
    ]
    for index in range(1, 11):
        url = browser_urls[(index - 1) % len(browser_urls)]
        tasks.append(
            task(
                f"browser-{index:03d}",
                "browser",
                difficulties[index - 1],
                f"请浏览 {url} 并抓取页面标题，任务编号 {index}。",
                required_tools=["browser.fetch"],
                min_observations=1,
                tags=["network", "browser", "public-web"],
            )
        )

    github_queries = [
        "agent runtime",
        "model context protocol",
        "llm evaluation",
        "workflow checkpoint",
        "distributed tracing",
        "deepseek",
        "docker sandbox",
        "react agent",
        "tool calling",
        "fastapi",
    ]
    for index, query in enumerate(github_queries, start=1):
        tasks.append(
            task(
                f"github-{index:03d}",
                "github",
                difficulties[index - 1],
                f"请使用 GitHub 搜索仓库：{query}，返回前几个结果的名称。",
                required_tools=["github.search_repositories"],
                min_observations=1,
                tags=["network", "github", "search"],
            )
        )

    mixed_values = [(11, 4, 15), (20, 5, 25), (9, 8, 17), (14, 6, 20), (8, 7, 15),
                    (18, 3, 21), (13, 12, 25), (7, 6, 13), (16, 9, 25), (10, 10, 20)]
    for index, (left, right, answer) in enumerate(mixed_values, start=1):
        tasks.append(
            task(
                f"mixed-{index:03d}",
                "mixed",
                "hard",
                (
                    f"先读取 examples/demo.txt，再使用 Python 计算 "
                    f"{left} + {right}。任务编号 {index}。"
                ),
                required_tools=["filesystem.read_file", "sandbox.run_python"],
                answer_contains=[str(answer)],
                min_observations=2,
                tags=["offline", "mixed", "filesystem", "sandbox"],
            )
        )

    return tasks


def main() -> None:
    output = Path("evals/dataset/seed_tasks.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    tasks = build_tasks()
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for item in tasks:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Wrote {len(tasks)} tasks to {output}")


if __name__ == "__main__":
    main()
