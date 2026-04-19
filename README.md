# Ollama Agent Simulation

Streamlit app simulating two autonomous AI agents — a **Provider** and a **Consumer** — communicating with each other using local Ollama inference. No API keys required.

## Architecture

- **Provider Agent**: manages a product catalog (`catalog.txt`), can read stock and update quantities.
- **Consumer Agent**: acts as a shopping assistant, queries and purchases from the Provider by calling its agent loop directly.
- Each agent runs its own `while`-loop until all tool calls are resolved.
- The right panel shows the real-time inter-agent message log.

## Setup (Ubuntu)

1. Install Ollama (runs as a systemd service automatically):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Pull model:
   ```bash
   ollama pull qwen3:4b
   ```
3. Install deps with uv:
   ```bash
   uv sync
   ```
4. Run:
   ```bash
   uv run streamlit run app.py
   ```

No API key required. Ollama starts automatically on Ubuntu — no need to run `ollama serve` manually.

## Project Structure

```
├── app.py               # Streamlit UI
├── consumer_agent.py    # Consumer agent loop + tools
├── provider_agent.py    # Provider agent loop + tools
├── catalog.txt          # Product inventory (read/written at runtime)
├── pyproject.toml       # uv project config
└── uv.lock
```
