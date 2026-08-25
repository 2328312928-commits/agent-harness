# Real Model Benchmark

The checked-in harness regression result uses `FakeProvider`. A resume metric should
come from a real model such as DeepSeek, with the provider version and run ID recorded.

## Run Locally

Set the provider key in a local `.env` file. The file is ignored by Git.

```dotenv
DEFAULT_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-key
DEEPSEEK_MODEL=deepseek-chat
```

Run the full suite:

```bash
python scripts/run_benchmark.py \
  --provider deepseek \
  --model deepseek-chat \
  --limit 110 \
  --concurrency 3
```

The run writes:

- Raw result: `evals/results/deepseek-benchmark-*.json`
- Report: `docs/benchmarks/deepseek-benchmark-*.md`

Do not overwrite `docs/benchmark-report.md`, which remains the deterministic harness
regression report.

## Run in GitHub Actions

1. Open repository `Settings -> Secrets and variables -> Actions`.
2. Add a repository secret named `DEEPSEEK_API_KEY`.
3. Open `Actions -> Model Benchmark -> Run workflow`.
4. Keep `provider=deepseek`, `model=deepseek-chat`, `limit=110`, `concurrency=3`.
5. Download the `model-benchmark-*` artifact after completion.

The workflow deliberately requires a manually configured secret and does not expose it
to pull requests.

## Reporting Rule

Only publish a model-quality metric after the run completes with the real provider.
Record the exact model, commit SHA, task count, concurrency, prompt strategy, latency,
tool accuracy, token usage, and estimated cost together.

