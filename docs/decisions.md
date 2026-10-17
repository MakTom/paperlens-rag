# Decisions

## Day 1
- Python 3.12 matches the course baseline.
- Only httpx and pydantic-settings are direct dependencies today.
- HTTP model access keeps local inference dependencies outside the Python application.
- Ollama is the initial generation provider; a small model is a connectivity baseline, not a final model-quality choice.
- Configuration lives in a validated Settings object; .env stays local.
- No database, vector search or PDF parser is started until its implementation day.
- Synchronous HTTP is sufficient for today's CLI. Revisit async access when integrating the API.
- On unsupported Mac hardware/OS, record the blocker before selecting a remote or hosted provider. This starter does not implement a hosted-provider adapter.
