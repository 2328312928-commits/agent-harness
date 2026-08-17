# Deployment

## Docker Compose

Compose is the complete local deployment because the Docker socket is available to the
API container:

```bash
cp .env.example .env
docker compose up --build
```

The API listens on port 8000 and the web console listens on port 8080. On Linux, set
`DOCKER_GID` to the host group that owns `/var/run/docker.sock`.

## Render Blueprint

`render.yaml` provisions PostgreSQL, the FastAPI API, and the static React console.

1. Push the repository to GitHub.
2. In Render, create a Blueprint from the repository.
3. Confirm the service names and `CORS_ORIGINS` match the generated console URL.
4. Update `VITE_API_URL` if Render changes the API hostname.

The free Render demo uses the deterministic provider. Code execution tools fail safely
because managed container platforms do not expose a Docker socket. Other tools, traces,
checkpoints, recovery, memory, and evaluation remain available. For production code
execution, deploy the sandbox as a remote worker or use a managed sandbox service.

## Environment

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLite for local tests or PostgreSQL for deployment |
| `DEFAULT_PROVIDER` | `fake`, `deepseek`, or `openai-compatible` |
| `WORKSPACE_ROOT` | Allowed filesystem root |
| `SANDBOX_BACKEND` | `docker` or explicitly opted-in `local` |
| `DOCKER_GID` | Host Docker socket group on Linux |
| `GITHUB_TOKEN` | Optional GitHub API rate-limit increase |
| `MCP_SERVERS_JSON` | External MCP server configuration |

## Production Sandbox

Mounting the Docker socket into the API is acceptable for a local demo, but not for a
multi-tenant production service. The production path is:

1. Keep untrusted code outside the API process.
2. Run a dedicated sandbox worker pool with gVisor, Firecracker, or Kata Containers.
3. Authenticate each execution request and enforce tenant quotas.
4. Store code and output artifacts in short-lived object storage.
5. Return only signed, size-limited results to the runtime.

