# Ollama Agent Simulation

Streamlit app simulating two autonomous AI agents — a **Provider** and a **Consumer** — communicating with each other using local Ollama inference. No API keys required.

## Architecture

- **Provider Agent**: manages a product catalog (`catalog.txt`), can read stock and update quantities.
- **Consumer Agent**: acts as a shopping assistant, queries and purchases from the Provider by calling its agent loop directly.
- Each agent runs its own `while`-loop until all tool calls are resolved.
- The right panel shows the real-time inter-agent message log.

## Setup

1. Install Ollama: https://ollama.com/download
2. Start Ollama: `ollama serve`
3. Pull model: `ollama pull qwen3:4b`
4. Install deps: `pip install -r requirements.txt`
5. Run: `streamlit run app.py`

No API key required.

## Project Structure

```
├── app.py               # Streamlit UI
├── consumer_agent.py    # Consumer agent loop + tools
├── provider_agent.py    # Provider agent loop + tools
├── catalog.txt          # Product inventory (read/written at runtime)
└── requirements.txt
```
