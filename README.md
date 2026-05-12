# Agent Sim

Multi-agent simulation framework for testing agent communication, coordination, and evaluation.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## About

Agent Sim is a multi-agent simulation framework for defining, running, and evaluating communication and coordination scenarios between multiple agents. Supports declarative YAML configuration, pluggable LLM backends, tool calling, and is suitable for research and testing of multi-agent interaction patterns.

## Features

### Agent System
- **Agent ABC** - Unified base class, subclasses only implement `step()`
- **LLMAgent** - Pluggable LLM backend (OpenAI / Ollama / local models), auto conversation history
- **ToolAgent** - Register and call tool functions, message-triggered tool execution
- **Role** - Role definition with name, description, and goals

### Communication
- **MessageBus** - Inter-agent message bus, direct/broadcast routing
- **Message** - Pydantic message model (sender, receiver, content, type)
- **Dead Letter** - Undeliverable messages auto-recorded

### LLM Backends (NEW in v0.3.0)
- **OpenAIBackend** - OpenAI-compatible API (OpenAI, Azure, vLLM, LiteLLM)
- **OllamaBackend** - Ollama local model server
- **create_backend()** - Factory function for config-driven backend selection
- Automatic API key resolution from environment variables
- Configurable timeout, temperature, max_tokens per backend

### Scenarios
- **ScenarioConfig** - Declarative scenario config with YAML support
- **ScenarioRunner** - Multi-step simulation loop, auto metrics collection
- **Factory** - Build agents, sandbox, and message bus from config

### Environment & Evaluation
- **Sandbox** - Simulation sandbox, manages agent collection and environment state
- **EnvironmentState** - Shared key-value store + event log
- **MetricsCollector** - Step-level metrics (message count, agent states, etc.)

### CLI
- `agent-sim run --example` - Run built-in example
- `agent-sim run --config scene.yaml` - Run from YAML config
- `agent-sim validate scene.yaml` - Validate scenario config
- `agent-sim info` - Framework info

## Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.10+ |
| Data validation | Pydantic v2 |
| CLI | Click |
| Config | PyYAML |
| HTTP | httpx |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Linting | Ruff |

## Project Structure

```
agent-sim/
├── src/agent_sim/
│   ├── __init__.py              # Top-level exports
│   ├── cli.py                   # CLI entry point
│   ├── log.py                   # Logging config
│   ├── agent/
│   │   ├── base.py              # Agent ABC + AgentState
│   │   ├── role.py              # Role definition
│   │   ├── llm_agent.py         # LLMAgent + LLMBackend ABC
│   │   ├── llm_backend.py       # OpenAIBackend, OllamaBackend, create_backend()
│   │   └── tool_agent.py        # ToolAgent + Tool
│   ├── communication/
│   │   ├── message.py           # Message + MessageType
│   │   └── bus.py               # MessageBus
│   ├── environment/
│   │   ├── state.py             # EnvironmentState
│   │   └── sandbox.py           # Sandbox
│   ├── scenario/
│   │   ├── config.py            # ScenarioConfig + YAML loader
│   │   ├── factory.py           # Config -> Sandbox/Bus builder
│   │   └── runner.py            # ScenarioRunner + RunResult
│   └── metrics/
│       └── collector.py         # MetricsCollector
├── tests/                       # 175 tests
├── scenarios/                   # Example YAML scenarios
└── examples/                    # Python example scripts
```

## Installation

```bash
git clone https://github.com/Jane-o-O-o-O/agent-sim.git
cd agent-sim
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick Start

### Python API

```python
from agent_sim import Agent, Sandbox, MessageBus, Message, ScenarioRunner
from agent_sim import LLMAgent, ToolAgent, load_scenario, build_scenario

# Method 1: Programmatic
class MyAgent(Agent):
    async def step(self):
        replies = []
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=f"echo:{msg.content}",
            ))
        self.inbox.clear()
        self.increment_step()
        return replies

sandbox = Sandbox(agents=[MyAgent(name="a"), MyAgent(name="b")])
bus = MessageBus()
# ... register and run

# Method 2: YAML configuration
config = load_scenario("scenarios/ping_pong.yaml")
sandbox, bus = build_scenario(config)
runner = ScenarioRunner(sandbox=sandbox, bus=bus)
result = await runner.run(steps=config.steps)
```

### LLM Backend Usage (v0.3.0)

```python
from agent_sim import LLMAgent, OpenAIBackend, OllamaBackend, create_backend

# OpenAI-compatible API
backend = OpenAIBackend(
    api_key="sk-...",
    model="gpt-4o",
    temperature=0.7,
)
agent = LLMAgent(name="assistant", backend=backend, system_prompt="You are helpful.")

# Ollama local models
backend = OllamaBackend(model="llama3", base_url="http://gpu-server:11434")
agent = LLMAgent(name="local-assistant", backend=backend)

# Factory function
backend = create_backend("openai", api_key="sk-...", model="gpt-4o-mini")
backend = create_backend("ollama", model="mistral")

# YAML config with LLM
# agents:
#   - name: assistant
#     type: llm
#     llm_backend: openai
#     llm_model: gpt-4o
#     context:
#       api_key: sk-...
#       system_prompt: "You are a helpful assistant."
```

### CLI

```bash
# Run built-in example
agent-sim run --example --steps 5

# Run from YAML config
agent-sim run --config scenarios/ping_pong.yaml

# Validate config
agent-sim validate scenarios/ping_pong.yaml

# Verbose logging
agent-sim -v run --config scenarios/ping_pong.yaml
```

## Agent Types

| Type | Description |
|------|------------|
| `echo` | Echo back received messages |
| `ping` | Send ping on first step, reply pong to pings |
| `llm` | LLM-driven agent, pluggable backend |
| `tool` | Tool-calling agent, message triggers tool execution |
| `custom` | Custom Agent class (specify module and class_name) |

## Roadmap

- [x] **v0.1.0** - Agent base class + MessageBus
- [x] **v0.2.0** - YAML config, LLMAgent, ToolAgent, logging
- [x] **v0.3.0** - LLM backend integrations (OpenAI, Ollama)
- [ ] **v0.4.0** - Advanced metrics & visualization
- [ ] **v1.0.0** - Stable API, complete documentation

## License

MIT License (c) 2026 Jane-o-O-o-O
