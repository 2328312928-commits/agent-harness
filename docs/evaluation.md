# Evaluation Data Card

## Dataset

- File: `evals/dataset/seed_tasks.jsonl`
- Size: 110 tasks
- Format: one JSON object per line
- Categories: reasoning, filesystem read/list, coding, database, memory, recovery,
  context compaction, browser, GitHub, mixed tools

## Task Schema

```json
{
  "id": "mixed-001",
  "category": "mixed",
  "difficulty": "hard",
  "goal": "Read a file and calculate a result",
  "expected": {
    "status": "completed",
    "required_tools": ["filesystem.read_file", "sandbox.run_python"],
    "answer_contains": ["19"],
    "min_observations": 2,
    "min_recoveries": 0
  },
  "max_steps": 12,
  "tags": ["offline", "mixed"],
  "fixture": {}
}
```

## Grading

Each task is graded on five checks:

1. Runtime status
2. Minimum observation count
3. Required answer fragments
4. Recovery count
5. Required tool set

The final score is the fraction of checks that pass. Success requires all checks.

## Provider Interpretation

The checked-in report uses `FakeProvider`. It validates the harness, not language-model
quality. To produce a model benchmark:

```bash
export DEFAULT_PROVIDER=deepseek
export DEEPSEEK_API_KEY=...
python scripts/run_benchmark.py
```

For a publishable model comparison, keep dataset version, prompt strategy, model version,
temperature, concurrency, and provider endpoints fixed in the report.

