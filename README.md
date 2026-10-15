# Card Dispute Intake Assistant

[![CI](https://github.com/t-sree/card-dispute-intake-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/t-sree/card-dispute-intake-assistant/actions/workflows/ci.yml)

Agent-assist tool that helps bank customer service agents capture a complete card dispute case during the first conversation.

> Work in progress. See [docs/project-brief.md](docs/project-brief.md) for the full project brief.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
```
