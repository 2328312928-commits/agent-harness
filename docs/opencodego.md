# OpenCodeGo Provider

OpenCodeGo exposes an OpenAI-compatible endpoint at:

```text
https://opencode.ai/zen/go/v1
```

Configure it in `.env`:

```dotenv
DEFAULT_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your-key
OPENAI_COMPATIBLE_BASE_URL=https://opencode.ai/zen/go/v1
OPENAI_COMPATIBLE_MODEL=deepseek-v4.1-flash
```

Available DeepSeek models currently include:

- `deepseek-v4-pro`
- `deepseek-v4.1-flash`
- `deepseek-v4-flash`
- `deepseek-v4-flash-vision-exp`

The provider sends:

- `User-Agent: agent-harness/0.2.1`
- `x-opencode-session: <task-id>`

The session header is required for routing and prompt caching. DeepSeek thinking models
also return `reasoning_content`; the runtime persists that field in assistant message
history because OpenCodeGo requires it to be passed back on follow-up calls.

